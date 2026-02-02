"""Settings and configuration management."""

from pathlib import Path
from pydantic import Field
from pydantic import AliasChoices
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # Application
    app_name: str = Field(default="spendmend_agent_builder", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./my_agent_data.db",
        description="Database URL for session storage and telemetry",
    )

    # Telemetry & Logging
    debug_log_path: str = Field(
        default="./logs/adk_debug.yaml",
        description="Path for YAML debug log file",
    )
    telemetry_enabled: bool = Field(
        default=True,
        description="Enable database-backed telemetry storage",
    )

    # Artifacts
    artifact_root_dir: str = Field(
        default="./artifacts",
        description="Root directory for artifact storage",
    )

    # Context Cache
    context_cache_enabled: bool = Field(default=True, description="Enable context caching")
    context_cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    context_cache_max_entries: int = Field(default=256, description="Maximum cache entries")

    # Jira
    jira_url: str = Field(
        default="https://your-org.atlassian.net",
        description="Jira instance URL",
        validation_alias=AliasChoices("JIRA_URL", "JIRA_BASE_URL"),
    )
    jira_email: Optional[str] = Field(
        default=None,
        description="Jira user email",
        validation_alias=AliasChoices("JIRA_EMAIL", "JIRA_USER_EMAIL"),
    )
    jira_api_token: Optional[str] = Field(
        default=None,
        description="Jira API token",
        validation_alias=AliasChoices("JIRA_API_TOKEN", "JIRA_API_KEY"),
    )

    # GitHub
    github_token: Optional[str] = Field(
        default=None,
        description="GitHub personal access token",
        validation_alias=AliasChoices("GITHUB_TOKEN", "GITHUB_API_TOKEN"),
    )

    # Databricks
    databricks_profile: Optional[str] = Field(
        default=None,
        description="Databricks CLI profile name (from ~/.databrickscfg)",
        validation_alias=AliasChoices("DATABRICKS_PROFILE", "DBX_PROFILE"),
    )
    databricks_host: Optional[str] = Field(
        default=None,
        description="Databricks workspace host (e.g., https://your-workspace.cloud.databricks.com)",
        validation_alias=AliasChoices("DATABRICKS_HOST", "DBX_HOST"),
    )
    databricks_token: Optional[str] = Field(
        default=None,
        description="Databricks personal access token",
        validation_alias=AliasChoices("DATABRICKS_TOKEN", "DBX_TOKEN"),
    )
    databricks_warehouse_id: Optional[str] = Field(
        default=None,
        description="Default SQL warehouse HTTP path (e.g. /sql/1.0/warehouses/<id>)",
        validation_alias=AliasChoices("DATABRICKS_WAREHOUSE_ID", "DATABRICKS_HTTP_PATH", "DBX_WAREHOUSE_ID"),
    )

    # Gemini API
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key (if not using default credentials)"
    )

    # Workspace
    workspace_root: str = Field(
        default="./workspace",
        description="Root directory for local workspace operations",
    )

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
