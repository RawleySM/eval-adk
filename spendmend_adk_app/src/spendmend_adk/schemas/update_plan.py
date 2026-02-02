"""Schemas for agent updater (proposes changes to tools/prompt/context/schemas)."""

from pydantic import BaseModel, Field
from typing import List, Literal


class AgentUpdaterInput(BaseModel):
    """Input schema for agent updater."""

    gap_report_output_json: str = Field(
        description="JSON from session.state['gap_reporter.output_json']"
    )
    current_agent_manifest_json: str = Field(
        description="Machine-readable spec of spendmend_dev (tools, prompts, schemas, cache settings)"
    )


class SchemaChange(BaseModel):
    """Represents a proposed schema change."""

    target: Literal["input_schema", "output_schema", "output_key"]
    change: str = Field(description="What to change and why")


class ToolChange(BaseModel):
    """Represents a proposed tool change."""

    action: Literal["ADD", "REMOVE", "MODIFY"]
    tool_name: str
    rationale: str


class PromptChange(BaseModel):
    """Represents a proposed prompt change."""

    file: str
    diff_summary: str


class AgentUpdaterOutput(BaseModel):
    """Output schema for agent updater."""

    tool_changes: List[ToolChange]
    schema_changes: List[SchemaChange]
    prompt_changes: List[PromptChange]
    context_cache_tuning: List[str] = Field(default_factory=list)
    migration_notes: List[str] = Field(default_factory=list)
