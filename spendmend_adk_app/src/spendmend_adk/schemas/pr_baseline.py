"""Schemas for baseline fetcher agent (human PR merged output)."""

from pydantic import BaseModel, Field
from typing import List, Optional
from .common import RepoRef, ArtifactRef


class BaselineFetchInput(BaseModel):
    """Input schema for baseline fetcher agent."""

    repo: RepoRef
    # Optionally: explicit PR URL if not in repo ref
    pr_url: Optional[str] = None


class BaselineFileChange(BaseModel):
    """Represents a file change in the baseline PR."""

    path: str
    additions: int
    deletions: int


class BaselineFetchOutput(BaseModel):
    """Output schema for baseline fetcher agent."""

    merged_sha: str
    files_changed: List[BaselineFileChange]
    baseline_patch_artifact: ArtifactRef = Field(
        description="Unified diff or patch saved as artifact"
    )
