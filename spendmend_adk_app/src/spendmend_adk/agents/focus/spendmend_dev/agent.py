"""Spendmend developer agent - the agent-of-focus.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LlmAgent
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.planners.BuiltInPlanner
"""

from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types
import os

from spendmend_adk.schemas.dev_task import SpendmendDevInput, SpendmendDevOutput
from spendmend_adk.tools.jira_tools import (
    jira_get_issue,
    jira_search_assigned,
    jira_add_comment,
)
from spendmend_adk.tools.github_tools import (
    gh_clone_at_ref,
    gh_read_file,
    gh_list_tree,
)
from spendmend_adk.tools.databricks_sql_tools import (
    dbx_sql_query,
    dbx_list_tables,
    dbx_describe_table,
    dbx_get_table_sample,
)
from spendmend_adk.tools.openapi_toolsets import openapi_toolsets_for_agents
from spendmend_adk.tools.artifact_tools import write_code_artifact
from spendmend_adk.tools.fs_tools import (
    read_local_file,
    write_local_file,
    list_directory,
)


# Load instruction from prompt file
_prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
with open(_prompt_path) as f:
    _instruction = f.read()


spendmend_dev = LlmAgent(
    name="spendmend_dev",
    model="gemini-2.5-flash",
    description=(
        "Developer agent: reads Jira, clones repo pre-merge, "
        "queries Databricks UC via SQL connector, writes code patches as artifacts."
    ),
    instruction=_instruction,
    # Built-in planner with thinking enabled
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
        )
    ),
    tools=[
        # OpenAPI-generated REST tools (Jira/GitHub/Databricks SQL REST subset)
        *openapi_toolsets_for_agents(),
        # Jira tools
        jira_search_assigned,
        jira_get_issue,
        jira_add_comment,
        # GitHub tools
        gh_clone_at_ref,
        gh_list_tree,
        gh_read_file,
        # Databricks SQL tools
        dbx_sql_query,
        dbx_list_tables,
        dbx_describe_table,
        dbx_get_table_sample,
        # Artifact tools
        write_code_artifact,
        # File system tools
        read_local_file,
        write_local_file,
        list_directory,
    ],
    # Structured I/O
    input_schema=SpendmendDevInput,
    output_schema=SpendmendDevOutput,
    output_key="spendmend_dev.output_json",
)
