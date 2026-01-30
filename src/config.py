from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    github_token: str
    llm_token: str
    repo_name: str = "Kokande/WEB-project-yan"

    model_config = SettingsConfigDict(
        env_file=(
            'cfg/secret.properties',
            'cfg/service.properties'
        ),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )


settings = Settings()