from config import settings

import logging
from typing import List, TypedDict, Any
from github import Github, Repository, GithubException

from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    repo: Any 
    repo_full_name: str
    issue_title: str
    issue_desc: str
    branch_name: str
    messages: List[BaseMessage]


@tool
def list_files(repo_full_name: str, path: str = "") -> str:
    """
    Lists files in a specific directory of the GitHub repository.
    Args:
        repo_full_name: The owner/repo string (e.g. 'langchain/langchain')
        path: The directory path to list (default is root)
    """
    g = Github(settings.github_token)
    repo = g.get_repo(repo_full_name)
    try:
        contents = repo.get_contents(path)
        files = []
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            else:
                files.append(file_content.path)
        return "\n".join(files[:50])
    except Exception as e:
        return f"Error listing files: {str(e)}"


@tool
def read_file(repo_full_name: str, file_path: str) -> str:
    """
    Reads the content of a specific file.
    Args:
        repo_full_name: The owner/repo string
        file_path: The full path to the file
    """
    g = Github(settings.github_token)
    repo = g.get_repo(repo_full_name)
    try:
        contents = repo.get_contents(file_path)
        return contents.decoded_content.decode("utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def update_file(repo_full_name: str, file_path: str, new_content: str, commit_message: str, branch: str) -> str:
    """
    Updates or creates a file in the repository on a specific branch.
    """
    g = Github(settings.github_token)
    repo = g.get_repo(repo_full_name)

    try:
        try:
            repo.get_branch(branch)
        except GithubException:
            source = repo.get_branch(repo.default_branch)
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.commit.sha)

        try:
            contents = repo.get_contents(file_path, ref=branch)
            repo.update_file(contents.path, commit_message, new_content, contents.sha, branch=branch)
            return f"Updated {file_path} on {branch}"
        except GithubException:
            repo.create_file(file_path, commit_message, new_content, branch=branch)
            return f"Created {file_path} on {branch}"

    except Exception as e:
        return f"Error committing to file: {str(e)}"


def agent_node(state: AgentState):
    logger.info(f"Code agents state: {state}")

    repo_name = state["repo_full_name"]

    llm = GigaChat(
        model="Gigachat-2-Max",
        temperature=0,
        verify_ssl_certs=False,
        credentials=settings.llm_token,
        scope="GIGACHAT_API_PERS"
    )
    tools = [list_files, read_file, update_file]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content=f"""
    Ты агент-кодер. Репозиторий: {repo_name}.

    Задача: Исправить проблему "{state['issue_title']}"
    Контекст: {state['issue_desc']}
    Целевая ветка: {state['branch_name']}
    
    1. Изучите код (`list_files`, `read_file`).
    2. Создайте/Обновите файлы (`update_file`). *Всегда* передавайте '{repo_name}' в качестве аргумента repo_full_name.
    3. После завершения ответь строго "READY_FOR_PR".
    """)

    messages = state["messages"]

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [sys_msg] + messages

    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "create_pr"


def create_pr_node(state: AgentState):
    repo = state["repo"]
    title = f"Fix: {state['issue_title']}"
    body = f"Automated PR for: {state['issue_desc']}"

    try:
        pr = repo.create_pull(
            title=title,
            body=body,
            head=state["branch_name"],
            base=repo.default_branch
        )
        return {"messages": [AIMessage(content=f"PR Created: {pr.html_url}")]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"PR Failed: {str(e)}")]}


def run_coding_agent(repo: Repository, issue_title: str, issue_desc: str) -> str:
    """
    The main entry point to run the agent.

    Args:
        repo: A PyGithub Repository object.
        issue_title: Title of the issue to fix.
        issue_desc: Detailed description of the issue.

    Returns:
        str: The final output (e.g., the PR URL or error message).
    """

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode([list_files, read_file, update_file]))
    workflow.add_node("create_pr", create_pr_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, ["tools", "create_pr"])
    workflow.add_edge("tools", "agent")
    workflow.add_edge("create_pr", END)

    app = workflow.compile(
        checkpointer=InMemorySaver()
    )

    safe_title = "".join(c if c.isalnum() else "-" for c in issue_title.lower())[:30]
    branch_name = f"agent/fix-{safe_title}"

    initial_state = {
        "repo": repo,
        "repo_full_name": repo.full_name,
        "issue_title": issue_title,
        "issue_desc": issue_desc,
        "branch_name": branch_name,
        "messages": [HumanMessage(content="Приступай к диагностике и исправлению.")]
    }

    logger.info(f"--- Agent Started on {repo.full_name} (Branch: {branch_name}) ---")
    final_output = ""

    for event in app.stream(initial_state, {"configurable": {"thread_id": "1"}}):
        for key, value in event.items():
            if key == "agent":
                msg = value["messages"][-1]
                logger.info(f"Agent: {msg.content}")
            elif key == "create_pr":
                final_output = value["messages"][-1].content
                logger.info(f"System: {final_output}")

    return final_output
