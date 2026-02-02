"""Root workflow loop - orchestrates the ticket processing pipeline.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.LoopAgent
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.agents.SequentialAgent
"""

from google.adk.agents import LoopAgent, SequentialAgent

from spendmend_adk.agents.builders.baseline_fetcher.agent import baseline_fetcher
from spendmend_adk.agents.focus.spendmend_dev.agent import spendmend_dev
from spendmend_adk.agents.builders.gap_reporter.agent import gap_reporter
from spendmend_adk.agents.builders.agent_updater.agent import agent_updater
from spendmend_adk.agents.builders.patch_writer.agent import patch_writer
from spendmend_adk.agents.builders.eval_runner.agent import eval_runner, completion_checker


def build_root_agent() -> LoopAgent:
    """
    Build the root agent that orchestrates the ticket processing loop.

    The workflow:
    1. spendmend_dev: Agent-of-focus attempts to complete the Jira ticket
    2. baseline_fetcher: Fetches the merged PR (human baseline solution)
    3. gap_reporter: Compares agent output vs human baseline
    4. agent_updater: Proposes improvements based on gaps
    5. patch_writer: Implements the proposed changes
    6. eval_runner: Re-runs spendmend_dev and evaluates performance
    7. completion_checker: Checks if all tickets are done (escalate=True to stop loop)

    The loop continues until:
    - completion_checker sets escalate=True (all tickets done)
    - max_iterations is reached (safety limit)

    Returns:
        Configured LoopAgent that orchestrates the entire workflow
    """
    # One ticket pipeline = deterministic execution order
    # Each agent is LLM-powered but executes in sequence
    per_ticket_pipeline = SequentialAgent(
        name="ticket_pipeline",
        sub_agents=[
            spendmend_dev,       # Agent-of-focus attempts task
            baseline_fetcher,    # Fetch merged human PR baseline
            gap_reporter,        # Compare agent vs human
            agent_updater,       # Propose updates to focus agent
            patch_writer,        # Write edits (as artifacts/patchset)
            eval_runner,         # Rerun spendmend_dev and score
            completion_checker,  # If no tickets left: escalate=True -> LoopAgent stops
        ],
    )

    # Wrap in a LoopAgent for continuous improvement cycles
    return LoopAgent(
        name="spendmend_ticket_loop",
        sub_agents=[per_ticket_pipeline],
        max_iterations=10_000,  # Safety cap - unlikely to reach this
    )
