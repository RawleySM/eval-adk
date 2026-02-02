"""Schemas for patch writer and eval runner agents."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from .common import ArtifactRef


class PatchWriterInput(BaseModel):
    """Input schema for patch writer agent."""

    agent_update_plan_json: str = Field(
        description="JSON from session.state['agent_updater.output_json']"
    )
    repo_workdir: str = Field(description="Local path where focus agent code lives")


class PatchWriterOutput(BaseModel):
    """Output schema for patch writer agent."""

    patchset_artifact: ArtifactRef
    files_touched: List[str]
    notes: List[str] = Field(default_factory=list)

    # If true, LoopAgent would stop; keep false unless intentionally ending the loop
    escalate: bool = False


class EvalRunnerInput(BaseModel):
    """Input schema for eval runner agent."""

    jira_key: str
    rerun_reason: str
    spendmend_dev_input_json: str = Field(
        description="Original JSON input used for spendmend_dev, possibly updated"
    )
    baseline_fetcher_output_json: str


class EvalMetric(BaseModel):
    """Represents an evaluation metric."""

    name: str
    value: float
    pass_gate: bool
    notes: Optional[str] = None


class EvalRunnerOutput(BaseModel):
    """Output schema for eval runner agent."""

    overall_pass: bool
    metrics: List[EvalMetric]
    eval_report_artifact: ArtifactRef


class CompletionCheckInput(BaseModel):
    """Input schema for completion checker agent."""

    remaining_ticket_keys: List[str]


class CompletionCheckOutput(BaseModel):
    """Output schema for completion checker agent."""

    done: bool
    message: str
    escalate: bool
