"""Database schema and utilities for telemetry storage.

This module provides database models and utilities for storing agent telemetry
data in the same SQLite database used for session storage.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Optional, Dict, Any
import json

Base = declarative_base()


class AgentInvocation(Base):
    """Records each agent invocation with metadata."""

    __tablename__ = "agent_invocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invocation_id = Column(String(255), unique=True, nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    agent_name = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)  # success, error, timeout, etc.
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_session_user', 'session_id', 'user_id'),
        Index('idx_started_at', 'started_at'),
    )


class LLMInteraction(Base):
    """Records LLM API calls and responses."""

    __tablename__ = "llm_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invocation_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    model_name = Column(String(255), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    request_data = Column(JSON, nullable=True)  # Stores request parameters
    response_data = Column(JSON, nullable=True)  # Stores response content
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_invocation_timestamp', 'invocation_id', 'timestamp'),
        Index('idx_model_timestamp', 'model_name', 'timestamp'),
    )


class ToolExecution(Base):
    """Records tool/function calls made by the agent."""

    __tablename__ = "tool_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invocation_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    tool_name = Column(String(255), nullable=False, index=True)
    arguments = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    __table_args__ = (
        Index('idx_invocation_tool', 'invocation_id', 'tool_name'),
        Index('idx_timestamp', 'timestamp'),
    )


class SessionState(Base):
    """Snapshots of session state at various points."""

    __tablename__ = "session_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invocation_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    state_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_invocation_timestamp', 'invocation_id', 'timestamp'),
    )


class TelemetryDatabase:
    """Manages async database connections and operations for telemetry."""

    def __init__(self, db_url: str):
        """
        Initialize telemetry database connection.

        Args:
            db_url: Database URL (e.g., "sqlite+aiosqlite:///./my_agent_data.db")
        """
        self.db_url = db_url
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """Close database connection."""
        await self.engine.dispose()

    async def record_invocation(
        self,
        invocation_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ):
        """Record a new agent invocation."""
        async with self.async_session() as session:
            invocation = AgentInvocation(
                invocation_id=invocation_id,
                session_id=session_id,
                user_id=user_id,
                agent_name=agent_name,
                started_at=datetime.utcnow(),
            )
            session.add(invocation)
            await session.commit()

    async def complete_invocation(
        self,
        invocation_id: str,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """Mark an invocation as complete."""
        async with self.async_session() as session:
            result = await session.execute(
                f"SELECT * FROM agent_invocations WHERE invocation_id = '{invocation_id}'"
            )
            invocation = result.scalar_one_or_none()
            if invocation:
                invocation.completed_at = datetime.utcnow()
                invocation.status = status
                invocation.error_message = error_message
                await session.commit()

    async def record_llm_interaction(
        self,
        invocation_id: str,
        model_name: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """Record an LLM interaction."""
        async with self.async_session() as session:
            interaction = LLMInteraction(
                invocation_id=invocation_id,
                timestamp=datetime.utcnow(),
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                request_data=request_data,
                response_data=response_data,
                error_message=error_message,
            )
            session.add(interaction)
            await session.commit()

    async def record_tool_execution(
        self,
        invocation_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
    ):
        """Record a tool execution."""
        async with self.async_session() as session:
            # Serialize result if it's not JSON-serializable
            result_json = result
            if result is not None and not isinstance(result, (dict, list, str, int, float, bool, type(None))):
                try:
                    result_json = str(result)
                except Exception:
                    result_json = "<non-serializable>"

            execution = ToolExecution(
                invocation_id=invocation_id,
                timestamp=datetime.utcnow(),
                tool_name=tool_name,
                arguments=arguments,
                result=result_json,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
            )
            session.add(execution)
            await session.commit()

    async def record_session_state(
        self,
        invocation_id: str,
        state_data: Dict[str, Any],
    ):
        """Record a session state snapshot."""
        async with self.async_session() as session:
            state = SessionState(
                invocation_id=invocation_id,
                timestamp=datetime.utcnow(),
                state_data=state_data,
            )
            session.add(state)
            await session.commit()
