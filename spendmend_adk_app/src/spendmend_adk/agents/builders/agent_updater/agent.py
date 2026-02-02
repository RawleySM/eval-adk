"""Agent updater - proposes changes to tools/prompt/context/schemas.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
"""

from google.adk.agents import LlmAgent
import os

from spendmend_adk.schemas.update_plan import AgentUpdaterInput, AgentUpdaterOutput
from spendmend_adk.tools.artifact_tools import write_json_artifact, read_artifact


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


agent_updater = LlmAgent(
    name="agent_updater",
    model="gemini-2.5-flash",
    description="Converts gap reports into a concrete update plan for the focus agent.",
    instruction=_instruction,
    tools=[
        write_json_artifact,
        read_artifact,
    ],
    input_schema=AgentUpdaterInput,
    output_schema=AgentUpdaterOutput,
    output_key="agent_updater.output_json",
)
