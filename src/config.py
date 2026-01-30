import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    github_webhook_secret: str
    github_token: str
    repo_name: str = "Kokande/githubCodingAgent"

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