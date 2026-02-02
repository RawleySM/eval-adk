"""Baseline fetcher agent - retrieves merged PR as human baseline.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
"""

from google.adk.agents import LlmAgent
import os

from spendmend_adk.schemas.pr_baseline import BaselineFetchInput, BaselineFetchOutput
from spendmend_adk.tools.github_tools import gh_fetch_pr_patch, gh_get_pr_details, gh_get_file_changes
from spendmend_adk.tools.openapi_toolsets import openapi_toolsets_for_agents
from spendmend_adk.tools.artifact_tools import write_text_artifact


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


baseline_fetcher = LlmAgent(
    name="baseline_fetcher",
    model="gemini-2.5-flash",
    description="Fetches merged PR baseline (human solution) and stores patch as artifact.",
    instruction=_instruction,
    tools=[
        *openapi_toolsets_for_agents(),
        gh_fetch_pr_patch,
        gh_get_pr_details,
        gh_get_file_changes,
        write_text_artifact,
    ],
    input_schema=BaselineFetchInput,
    output_schema=BaselineFetchOutput,
    output_key="baseline_fetcher.output_json",
)
