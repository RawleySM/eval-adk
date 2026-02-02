"""Eval runner agent - reruns focus agent and evaluates performance.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
"""

from google.adk.agents import LlmAgent
import os

from spendmend_adk.schemas.eval import (
    EvalRunnerInput,
    EvalRunnerOutput,
    CompletionCheckInput,
    CompletionCheckOutput,
)
from spendmend_adk.tools.artifact_tools import write_json_artifact, read_artifact


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


eval_runner = LlmAgent(
    name="eval_runner",
    model="gemini-2.5-flash",
    description="Reruns focus agent and scores it against baseline; persists eval report.",
    instruction=_instruction,
    tools=[
        write_json_artifact,
        read_artifact,
    ],
    input_schema=EvalRunnerInput,
    output_schema=EvalRunnerOutput,
    output_key="eval_runner.output_json",
)


# Completion checker agent - signals loop termination
_completion_prompt = """
You check if all tickets are completed.

Given a list of remaining ticket keys:
- If the list is EMPTY: return done=true, escalate=true, message="All assigned tickets completed and documented."
- If the list has items: return done=false, escalate=false, message="Continue processing tickets."

Your response MUST be valid JSON matching the schema.
"""


completion_checker = LlmAgent(
    name="completion_checker",
    model="gemini-2.5-flash",
    description="Checks if ticket queue is empty; if yes, requests loop termination.",
    instruction=_completion_prompt,
    input_schema=CompletionCheckInput,
    output_schema=CompletionCheckOutput,
    output_key="completion_checker.output_json",
)
