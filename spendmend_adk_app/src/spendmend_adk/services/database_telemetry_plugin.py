"""Database-backed telemetry plugin for ADK agents.

This plugin extends the ADK plugin system to store telemetry data in a SQLite
database, enabling persistent storage, querying, and analysis of agent interactions.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.plugins
"""

import time
import uuid
from typing import Any, Optional, Dict
from datetime import datetime

from google.adk.plugins import BasePlugin
from google.adk.sessions import SessionState

from spendmend_adk.services.telemetry_db import TelemetryDatabase


class DatabaseTelemetryPlugin(BasePlugin):
    """
    Plugin that stores agent telemetry data in a database.

    This plugin captures:
    - Agent invocations and their outcomes
    - LLM API calls with token usage and latency
    - Tool/function executions
    - Session state snapshots

    All data is stored in the same database used for session storage,
    providing a unified data store for both operational and analytical needs.
    """

    def __init__(
        self,
        db_url: str = "sqlite+aiosqlite:///./my_agent_data.db",
        name: str = "database_telemetry_plugin",
        include_session_state: bool = True,
        max_response_length: int = 10000,
    ):
        """
        Initialize the database telemetry plugin.

        Args:
            db_url: Database URL (uses same DB as session service)
            name: Plugin instance name
            include_session_state: Whether to capture session state snapshots
            max_response_length: Maximum length of stored response data (truncated if longer)
        """
        super().__init__(name=name)
        self.db_url = db_url
        self.include_session_state = include_session_state
        self.max_response_length = max_response_length
        self.db: Optional[TelemetryDatabase] = None
        self._current_invocation_id: Optional[str] = None
        self._invocation_start_time: Optional[float] = None
        self._llm_start_time: Optional[float] = None

    async def on_plugin_start(self) -> None:
        """Initialize database connection when plugin starts."""
        self.db = TelemetryDatabase(self.db_url)
        await self.db.init_db()

    async def on_plugin_end(self) -> None:
        """Close database connection when plugin ends."""
        if self.db:
            await self.db.close()

    async def on_invocation_start(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        session_state: SessionState,
        agent_name: str,
        **kwargs,
    ) -> None:
        """
        Called when an agent invocation starts.

        Records the start of a new invocation with metadata.
        """
        if not self.db:
            return

        # Generate unique invocation ID
        self._current_invocation_id = f"inv-{uuid.uuid4().hex[:12]}"
        self._invocation_start_time = time.time()

        await self.db.record_invocation(
            invocation_id=self._current_invocation_id,
            session_id=session_id,
            user_id=user_id,
            agent_name=agent_name,
        )

        if self.include_session_state:
            # Record initial session state
            try:
                state_dict = self._serialize_session_state(session_state)
                await self.db.record_session_state(
                    invocation_id=self._current_invocation_id,
                    state_data=state_dict,
                )
            except Exception as e:
                # Don't fail the invocation if state serialization fails
                print(f"Warning: Failed to serialize session state: {e}")

    async def on_invocation_end(
        self,
        *,
        user_id: str,
        session_id: str,
        response: str,
        session_state: SessionState,
        **kwargs,
    ) -> None:
        """
        Called when an agent invocation completes successfully.

        Records completion status and final session state.
        """
        if not self.db or not self._current_invocation_id:
            return

        await self.db.complete_invocation(
            invocation_id=self._current_invocation_id,
            status="success",
        )

        if self.include_session_state:
            # Record final session state
            try:
                state_dict = self._serialize_session_state(session_state)
                await self.db.record_session_state(
                    invocation_id=self._current_invocation_id,
                    state_data=state_dict,
                )
            except Exception as e:
                print(f"Warning: Failed to serialize final session state: {e}")

        # Reset invocation tracking
        self._current_invocation_id = None
        self._invocation_start_time = None

    async def on_invocation_error(
        self,
        *,
        user_id: str,
        session_id: str,
        error: Exception,
        **kwargs,
    ) -> None:
        """
        Called when an agent invocation fails with an error.

        Records error information for debugging.
        """
        if not self.db or not self._current_invocation_id:
            return

        error_message = f"{type(error).__name__}: {str(error)}"
        await self.db.complete_invocation(
            invocation_id=self._current_invocation_id,
            status="error",
            error_message=error_message,
        )

        # Reset invocation tracking
        self._current_invocation_id = None
        self._invocation_start_time = None

    async def on_llm_request(
        self,
        *,
        model: str,
        request: Dict[str, Any],
        **kwargs,
    ) -> None:
        """
        Called before making an LLM API request.

        Records the start time for latency measurement.
        """
        self._llm_start_time = time.time()

    async def on_llm_response(
        self,
        *,
        model: str,
        request: Dict[str, Any],
        response: Any,
        **kwargs,
    ) -> None:
        """
        Called after receiving an LLM API response.

        Records the interaction with token usage and latency.
        """
        if not self.db or not self._current_invocation_id:
            return

        # Calculate latency
        latency_ms = None
        if self._llm_start_time:
            latency_ms = (time.time() - self._llm_start_time) * 1000
            self._llm_start_time = None

        # Extract token usage if available
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None

        if hasattr(response, 'usage'):
            usage = response.usage
            prompt_tokens = getattr(usage, 'input_tokens', None) or getattr(usage, 'prompt_tokens', None)
            completion_tokens = getattr(usage, 'output_tokens', None) or getattr(usage, 'completion_tokens', None)
            total_tokens = getattr(usage, 'total_tokens', None)

            if total_tokens is None and prompt_tokens and completion_tokens:
                total_tokens = prompt_tokens + completion_tokens

        # Serialize request and response (truncate if too large)
        request_data = self._truncate_data(request)
        response_data = self._truncate_data(self._serialize_response(response))

        await self.db.record_llm_interaction(
            invocation_id=self._current_invocation_id,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            request_data=request_data,
            response_data=response_data,
        )

    async def on_llm_error(
        self,
        *,
        model: str,
        request: Dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> None:
        """
        Called when an LLM API request fails.

        Records the error for debugging.
        """
        if not self.db or not self._current_invocation_id:
            return

        # Calculate latency if available
        latency_ms = None
        if self._llm_start_time:
            latency_ms = (time.time() - self._llm_start_time) * 1000
            self._llm_start_time = None

        error_message = f"{type(error).__name__}: {str(error)}"
        request_data = self._truncate_data(request)

        await self.db.record_llm_interaction(
            invocation_id=self._current_invocation_id,
            model_name=model,
            latency_ms=latency_ms,
            request_data=request_data,
            error_message=error_message,
        )

    async def on_tool_call(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        **kwargs,
    ) -> None:
        """
        Called when a tool is about to be executed.

        Records the tool call with arguments.
        """
        if not self.db or not self._current_invocation_id:
            return

        # Note: We record this when we get the result in on_tool_result
        # This method is here for potential future use

    async def on_tool_result(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        **kwargs,
    ) -> None:
        """
        Called after a tool execution completes.

        Records the tool execution with arguments and result.
        """
        if not self.db or not self._current_invocation_id:
            return

        # Truncate arguments and result
        args_data = self._truncate_data(arguments)
        result_data = self._truncate_data(result)

        await self.db.record_tool_execution(
            invocation_id=self._current_invocation_id,
            tool_name=tool_name,
            arguments=args_data,
            result=result_data,
        )

    async def on_tool_error(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> None:
        """
        Called when a tool execution fails.

        Records the error for debugging.
        """
        if not self.db or not self._current_invocation_id:
            return

        error_message = f"{type(error).__name__}: {str(error)}"
        args_data = self._truncate_data(arguments)

        await self.db.record_tool_execution(
            invocation_id=self._current_invocation_id,
            tool_name=tool_name,
            arguments=args_data,
            error_message=error_message,
        )

    def _serialize_session_state(self, session_state: SessionState) -> Dict[str, Any]:
        """
        Serialize session state to a JSON-compatible dictionary.

        Args:
            session_state: The session state object

        Returns:
            Dictionary representation of the state
        """
        # ADK SessionState can be complex - extract what we can
        try:
            if hasattr(session_state, 'model_dump'):
                return session_state.model_dump()
            elif hasattr(session_state, 'dict'):
                return session_state.dict()
            else:
                return {"_raw": str(session_state)}
        except Exception as e:
            return {"_error": f"Failed to serialize: {str(e)}"}

    def _serialize_response(self, response: Any) -> Any:
        """
        Serialize LLM response to JSON-compatible format.

        Args:
            response: The LLM response object

        Returns:
            JSON-compatible representation
        """
        try:
            if hasattr(response, 'model_dump'):
                return response.model_dump()
            elif hasattr(response, 'dict'):
                return response.dict()
            elif isinstance(response, (dict, list, str, int, float, bool, type(None))):
                return response
            else:
                return str(response)
        except Exception:
            return str(response)

    def _truncate_data(self, data: Any) -> Any:
        """
        Truncate data if it exceeds maximum length.

        Args:
            data: Data to potentially truncate

        Returns:
            Original or truncated data
        """
        try:
            # Convert to string to check length
            data_str = str(data)
            if len(data_str) > self.max_response_length:
                return {
                    "_truncated": True,
                    "_length": len(data_str),
                    "_preview": data_str[:self.max_response_length],
                }
            return data
        except Exception:
            return data
