"""Plugin configuration for debugging and monitoring.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.plugins.DebugLoggingPlugin
"""

from google.adk.plugins import DebugLoggingPlugin
from typing import List

from spendmend_adk.services.database_telemetry_plugin import DatabaseTelemetryPlugin


def create_plugins(
    db_url: str = "sqlite+aiosqlite:///./my_agent_data.db",
    debug_log_path: str = "adk_debug.yaml",
    include_session_state: bool = True,
) -> List:
    """
    Create list of plugins for the ADK runner.

    Args:
        db_url: Database URL for telemetry storage (same as session service)
        debug_log_path: File path for YAML debug logs
        include_session_state: Whether to capture session state in logs

    Returns:
        List of configured plugin instances

    Note:
        Configured plugins:
        - DebugLoggingPlugin: Writes human-readable YAML logs to file
          - Useful for debugging and sharing logs
          - Captures LLM requests/responses, tool calls, session state
          - Output: YAML file (default: adk_debug.yaml)

        - DatabaseTelemetryPlugin: Stores telemetry in SQLite database
          - Persistent storage for analysis and querying
          - Captures invocations, LLM calls, tool executions
          - Uses same database as session service
          - Enables metrics tracking and cost analysis

        Both plugins run in parallel, providing:
        - File-based logs for immediate debugging
        - Database storage for long-term analysis and reporting
    """
    return [
        # YAML file-based debug logging
        DebugLoggingPlugin(
            output_path=debug_log_path,
            include_session_state=include_session_state,
            include_system_instruction=True,
        ),
        # Database-backed telemetry storage
        DatabaseTelemetryPlugin(
            db_url=db_url,
            include_session_state=include_session_state,
            max_response_length=10000,  # Truncate large responses
        ),
    ]
