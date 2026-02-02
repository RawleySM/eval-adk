"""Common schemas used across multiple agents."""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


class JiraRef(BaseModel):
    """Reference to a Jira issue."""

    key: str = Field(description="Jira issue key, e.g., SPEND-123")
    url: str
    title: str
    description: str


class RepoRef(BaseModel):
    """Reference to a repository and its state."""

    clone_url: str
    default_branch: str
    base_ref: str = Field(
        description="Commit SHA or branch name representing pre-merge state"
    )
    merged_pr_url: Optional[str] = None
    merged_sha: Optional[str] = None


class ArtifactRef(BaseModel):
    """Reference to a stored artifact."""

    filename: str = Field(
        description="Artifact filename/key, relative to artifact root"
    )
    revision: Optional[int] = None


class ToolCallSummary(BaseModel):
    """Summary of a tool call execution."""

    tool_name: str
    args: Dict[str, Any]
    ok: bool
    notes: Optional[str] = None
