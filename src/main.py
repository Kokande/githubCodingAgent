import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import uvicorn
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi import FastAPI, Request, Header
from pydantic import BaseModel

app = FastAPI(title="Coding Agent")
logger = logging.getLogger(__name__)


class Issue(BaseModel):
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: str
    user: Dict[str, Any]


class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool


class WebhookPayload(BaseModel):
    action: str
    issue: Optional[Issue] = None
    repository: Repository
    sender: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up GitHub Webhook Service...")
    yield
    logger.info("Shutting down...")


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "GitHub Webhook Receiver",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "POST /webhook",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }


@app.get("/agent/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def github_event(
        request: Request,
        body: bytes,
        x_github_event: str = Header(None, alias="X-GitHub-Event"),
):
    try:
        payload = json.loads(body.decode('utf-8'))

        logger.info(f"Received {x_github_event} event: "
                    f"Payload: {payload.get('action', 'unknown')}; "
                    f"Request: {request};")

        if x_github_event == "issues":
            action = payload.get('action')

            if action == "opened":
                # Agent code here
                return JSONResponse(
                    status_code=202,
                    content={"message": "Issue creation accepted for processing"}
                )

            elif action == "closed":
                logger.info(f"Issue #{payload['issue']['number']} was closed")

            elif action == "labeled":
                logger.info(f"Label added to issue #{payload['issue']['number']}")

        elif x_github_event == "issue_comment":
            action = payload.get('action')
            if action == "created":
                return JSONResponse(
                    status_code=202,
                    content={"message": "Comment processing started"}
                )

        elif x_github_event == "ping":
            return JSONResponse(
                status_code=200,
                content={"message": "Webhook is active"}
            )

        return JSONResponse(
            status_code=200,
            content={"message": "Event received"}
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)