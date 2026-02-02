"""Main entrypoint for the Spendmend ADK application."""

import asyncio
import json
import sys
from typing import List, Optional

from spendmend_adk.app_factory import build_runner
from spendmend_adk.settings import settings


async def run_ticket_loop(
    ticket_keys: List[str],
    user_id: str = "rawley",
    session_id: Optional[str] = None,
) -> None:
    """
    Run the agent loop for a list of Jira tickets.

    Args:
        ticket_keys: List of Jira ticket keys to process (e.g., ["SPEND-101", "SPEND-102"])
        user_id: User ID for session management (default: "rawley")
        session_id: Optional session ID. If not provided, a new session is created.
    """
    # Build the runner
    runner = build_runner()

    # Generate session ID if not provided
    if session_id is None:
        import uuid
        session_id = f"session-{uuid.uuid4().hex[:8]}"

    print(f"Starting agent loop for {len(ticket_keys)} tickets")
    print(f"Session ID: {session_id}")
    print(f"User ID: {user_id}")
    print(f"Tickets: {', '.join(ticket_keys)}")
    print("-" * 80)

    # Initial payload: seed the ticket queue
    initial_payload = {
        "remaining_ticket_keys": ticket_keys,
        # Additional configuration can go here:
        # - Repository references
        # - Credentials (or loaded from settings)
        # - Policies
        # - Constraints
    }

    try:
        # Run the agent loop
        await runner.run_async(
            user_id=user_id,
            session_id=session_id,
            message=json.dumps(initial_payload),
        )
        print("-" * 80)
        print("Agent loop completed successfully")
    except Exception as e:
        print("-" * 80)
        print(f"Error during agent loop: {e}", file=sys.stderr)
        raise


async def main() -> None:
    """
    Main entrypoint function.

    This is a minimal CLI that:
    1. Loads settings from environment
    2. Defines a list of tickets to process
    3. Runs the agent loop

    TODO: Replace this with a proper CLI using argparse or click
    TODO: Support reading tickets from Jira query
    TODO: Add resume capability for interrupted sessions
    """
    # Example ticket list - replace with real tickets
    ticket_keys = [
        "SPEND-101",
        "SPEND-102",
        # Add more tickets as needed
    ]

    # TODO: Add CLI argument parsing
    # import argparse
    # parser = argparse.ArgumentParser(description="Spendmend Agent Builder")
    # parser.add_argument("--tickets", nargs="+", help="Jira ticket keys to process")
    # parser.add_argument("--user-id", default="rawley", help="User ID")
    # parser.add_argument("--session-id", help="Session ID (generates new if not provided)")
    # args = parser.parse_args()

    # Run the ticket loop
    await run_ticket_loop(ticket_keys=ticket_keys)


if __name__ == "__main__":
    asyncio.run(main())
