"""Session service configuration for database-backed session storage.

ADK Docs:
- https://google.github.io/adk-docs/sessions/session/#databasesessionservice
"""

from google.adk.sessions import DatabaseSessionService


def create_session_service(db_url: str = "sqlite+aiosqlite:///./my_agent_data.db") -> DatabaseSessionService:
    """
    Create a DatabaseSessionService instance.

    Args:
        db_url: Database URL (default: SQLite with async driver)

    Returns:
        Configured DatabaseSessionService instance

    Note:
        The default uses sqlite+aiosqlite which provides async support.
        For production, consider using PostgreSQL or other robust databases.

        Example URLs:
        - SQLite: "sqlite+aiosqlite:///./my_agent_data.db"
        - PostgreSQL: "postgresql+asyncpg://user:pass@localhost/dbname"
    """
    return DatabaseSessionService(db_url=db_url)
