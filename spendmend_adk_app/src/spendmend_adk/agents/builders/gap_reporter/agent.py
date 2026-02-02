"""Gap reporter agent - compares agent output vs human baseline.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
"""

from google.adk.agents import LlmAgent
import os

from spendmend_adk.schemas.review import GapReportInput, GapReportOutput
from spendmend_adk.tools.artifact_tools import write_json_artifact, read_artifact


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


gap_reporter = LlmAgent(
    name="gap_reporter",
    model="gemini-2.5-flash",
    description="Compares spendmend_dev output vs merged PR baseline; produces structured gap report.",
    instruction=_instruction,
    tools=[
        write_json_artifact,
        read_artifact,
    ],
    input_schema=GapReportInput,
    output_schema=GapReportOutput,
    output_key="gap_reporter.output_json",
)
