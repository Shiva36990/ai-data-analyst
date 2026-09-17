"""
Centralized application configuration.

All environment-driven settings live here so the rest of the codebase
never touches os.environ directly.
"""

from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    app_env: str = os.getenv("APP_ENV", "development")

    max_query_rows: int = int(os.getenv("MAX_QUERY_ROWS", "500"))
    sql_timeout_ms: int = int(os.getenv("SQL_TIMEOUT_MS", "10000"))
    max_sql_retries: int = int(os.getenv("MAX_SQL_RETRIES", "2"))
    max_investigation_steps: int = int(
        os.getenv("MAX_INVESTIGATION_STEPS", "2")
    )


settings = Settings()


def validate_settings() -> list[str]:
    """Return a list of human-readable problems with the current config.

    Called at startup (app.py / scripts) so misconfiguration fails fast
    with a clear message instead of a confusing stack trace three layers
    deep in LangGraph.
    """
    problems = []

    if not settings.database_url:
        problems.append("DATABASE_URL is not set.")

    if not settings.google_api_key:
        problems.append("GOOGLE_API_KEY is not set.")

    if not settings.gemini_model:
        problems.append("GEMINI_MODEL is not set.")

    return problems
