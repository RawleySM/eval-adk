"""Schemas for gap reporter agent (comparing agent output vs human baseline)."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from .common import ArtifactRef


class GapReportInput(BaseModel):
    """Input schema for gap reporter agent."""

    spendmend_dev_output_json: str = Field(
        description="JSON string from session.state['spendmend_dev.output_json']"
    )
    baseline_fetcher_output_json: str = Field(
        description="JSON string from session.state['baseline_fetcher.output_json']"
    )


class GapItem(BaseModel):
    """Represents a gap between agent output and human baseline."""

    category: Literal[
        "MISSING_FILE",
        "WRONG_FILE",
        "INCORRECT_TRAJECTORY",
        "BAD_ASSUMPTION",
        "INSUFFICIENT_CONTEXT",
        "MISSED_TOOL_OPPORTUNITY",
        "SCHEMA_MISMATCH",
    ]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    description: str
    evidence: Optional[str] = None


class GapReportOutput(BaseModel):
    """Output schema for gap reporter agent."""

    summary: str
    gaps: List[GapItem]
    recommended_changes: List[str] = Field(
        description="Concrete recommendations for prompt/tools/context/schema"
    )
    report_artifact: Optional[ArtifactRef] = None
