"""Application factory - builds runner with all services and plugins.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.runners.Runner
"""

from google.adk.runners import Runner

from spendmend_adk.settings import settings
from spendmend_adk.services.session_service import create_session_service
from spendmend_adk.services.artifact_service import create_artifact_service
from spendmend_adk.services.context_cache import create_context_cache_config
from spendmend_adk.services.plugins import create_plugins
from spendmend_adk.agents.workflow.root_loop import build_root_agent


def build_runner() -> Runner:
    """
    Build the ADK runner with all services, plugins, and configuration.

    This is the main factory function that assembles:
    - DatabaseSessionService: SQLite (or other DB) for session storage
    - FileArtifactService: Filesystem-backed artifact storage
    - DebugLoggingPlugin: YAML file-based debug logging for agent interactions
    - DatabaseTelemetryPlugin: SQLite-backed telemetry storage (same DB as sessions)
    - ContextCacheConfig: Context caching for efficiency
    - Root Agent: The complete workflow orchestration

    The database stores both operational data (sessions) and analytical data
    (telemetry), providing a unified data store for monitoring, debugging, and
    cost analysis.

    Returns:
        Configured Runner ready to execute the agent workflow
    """
    # Create session service (database-backed)
    session_service = create_session_service(db_url=settings.database_url)

    # Create artifact service (filesystem-backed)
    artifact_service = create_artifact_service(root_dir=settings.artifact_root_dir)

    # Create plugins (debug logging and database telemetry)
    plugins = create_plugins(
        db_url=settings.database_url,
        debug_log_path=settings.debug_log_path,
        include_session_state=True,
    )

    # Create context cache config
    context_cache_config = create_context_cache_config(
        enabled=settings.context_cache_enabled,
        ttl_seconds=settings.context_cache_ttl_seconds,
        max_entries=settings.context_cache_max_entries,
    )

    # Build the root agent (workflow orchestration)
    root_agent = build_root_agent()

    # Create and return the runner
    runner = Runner(
        app_name=settings.app_name,
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service,
        plugins=plugins,
        context_cache_config=context_cache_config,
    )

    return runner
