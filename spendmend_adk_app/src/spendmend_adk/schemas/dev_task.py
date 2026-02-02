"""Schemas for the spendmend_dev agent (agent-of-focus)."""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from .common import JiraRef, RepoRef, ArtifactRef, ToolCallSummary


class SpendmendDevInput(BaseModel):
    """Input schema for the spendmend_dev agent."""

    jira: JiraRef
    repo: RepoRef

    goal: str = Field(description="What should be implemented/fixed for this ticket")
    constraints: List[str] = Field(default_factory=list)

    databricks_sql_warehouse_id: Optional[str] = None
    unity_catalog_targets: List[str] = Field(
        default_factory=list,
        description="Catalog/schema/table targets the agent may query",
    )

    eval_mode: bool = Field(
        default=False,
        description="If true, agent should be extra deterministic and verbose about decisions",
    )


class FileEdit(BaseModel):
    """Represents a file edit made by the agent."""

    path: str
    change_type: Literal["create", "modify", "delete"]
    rationale: str


class SpendmendDevOutput(BaseModel):
    """Output schema for the spendmend_dev agent."""

    status: Literal["DONE", "PARTIAL", "BLOCKED"]
    plan: List[str] = Field(description="High-level plan actually executed")
    file_edits: List[FileEdit]
    tests_run: List[str] = Field(default_factory=list)
    artifacts_written: List[ArtifactRef] = Field(default_factory=list)
    tool_calls: List[ToolCallSummary] = Field(default_factory=list)

    # Important for trajectory evaluation
    decisions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
