#!/usr/bin/env python3
"""Initialize the SQLite database for ADK session and telemetry storage.

This script creates all necessary tables for:
- Session storage (managed by DatabaseSessionService)
- Telemetry storage (agent invocations, LLM interactions, tool executions)

Usage:
    python scripts/init_database.py

The database URL is read from settings (default: sqlite+aiosqlite:///./my_agent_data.db)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spendmend_adk.settings import settings
from spendmend_adk.services.telemetry_db import TelemetryDatabase


async def init_database():
    """Initialize the database with all required tables."""
    print(f"Initializing database at: {settings.database_url}")
    print("-" * 80)

    # Initialize telemetry tables
    print("Creating telemetry tables...")
    db = TelemetryDatabase(settings.database_url)
    try:
        await db.init_db()
        print("✓ Telemetry tables created:")
        print("  - agent_invocations")
        print("  - llm_interactions")
        print("  - tool_executions")
        print("  - session_states")
    finally:
        await db.close()

    print()
    print("Note: Session service tables are created automatically by")
    print("      DatabaseSessionService on first use.")
    print()
    print("-" * 80)
    print("Database initialization complete!")
    print()
    print("Database file location:")
    # Extract file path from URL (e.g., sqlite+aiosqlite:///./my_agent_data.db)
    db_path = settings.database_url.split("///")[-1]
    db_path_absolute = Path(db_path).absolute()
    print(f"  {db_path_absolute}")
    print()
    print("You can inspect the database using:")
    print(f"  sqlite3 {db_path}")
    print()
    print("Example queries:")
    print("  SELECT * FROM agent_invocations;")
    print("  SELECT * FROM llm_interactions ORDER BY timestamp DESC LIMIT 10;")
    print("  SELECT tool_name, COUNT(*) FROM tool_executions GROUP BY tool_name;")


async def main():
    """Main entry point."""
    try:
        await init_database()
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
