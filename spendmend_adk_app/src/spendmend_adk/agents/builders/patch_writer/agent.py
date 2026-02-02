"""Patch writer agent - applies update plan to agent code.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
"""

from google.adk.agents import LlmAgent
import os

from spendmend_adk.schemas.eval import PatchWriterInput, PatchWriterOutput
from spendmend_adk.tools.artifact_tools import write_patchset_artifact, read_artifact
from spendmend_adk.tools.fs_tools import (
    read_local_file,
    write_local_file,
    list_directory,
    apply_patch_locally,
)


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


patch_writer = LlmAgent(
    name="patch_writer",
    model="gemini-2.5-flash",
    description="Applies update plan: edits prompts/tool wiring/schema definitions; writes patchset artifacts.",
    instruction=_instruction,
    tools=[
        write_patchset_artifact,
        read_artifact,
        read_local_file,
        write_local_file,
        list_directory,
        apply_patch_locally,
    ],
    input_schema=PatchWriterInput,
    output_schema=PatchWriterOutput,
    output_key="patch_writer.output_json",
)
