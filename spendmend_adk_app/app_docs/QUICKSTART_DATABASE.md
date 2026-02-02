# Quick Start: Database Setup for Sessions and Telemetry

This guide will help you get started with the SQLite database for ADK sessions and telemetry.

## 1. Verify Configuration

Check that your `.env` file has the database configuration:

```bash
cd spendmend_adk_app
cat .env | grep -E "DATABASE_URL|DEBUG_LOG|TELEMETRY"
```

You should see:
```
DATABASE_URL=sqlite+aiosqlite:///./my_agent_data.db
DEBUG_LOG_PATH=./logs/adk_debug.yaml
TELEMETRY_ENABLED=true
```

## 2. Initialize the Database

Run the initialization script to create all telemetry tables:

```bash
python scripts/init_database.py
```

This will create:
- `agent_invocations` - Track each agent run
- `llm_interactions` - Record all LLM API calls
- `tool_executions` - Log tool/function calls
- `session_states` - Snapshot session state

Session tables are created automatically by the ADK `DatabaseSessionService`.

## 3. Run Your Agent

The database and telemetry are now ready. When you run your agent:

```bash
python src/spendmend_adk/main.py
```

Both plugins will automatically record data:
- **DebugLoggingPlugin** → Writes to `./logs/adk_debug.yaml`
- **DatabaseTelemetryPlugin** → Writes to SQLite database

## 4. Inspect the Data

### Option A: SQLite CLI

```bash
sqlite3 my_agent_data.db
```

Example queries:
```sql
-- Recent invocations
SELECT invocation_id, agent_name, started_at, status
FROM agent_invocations
ORDER BY started_at DESC LIMIT 5;

-- Token usage
SELECT model_name, SUM(total_tokens) as total_tokens
FROM llm_interactions
GROUP BY model_name;

-- Tool usage
SELECT tool_name, COUNT(*) as count
FROM tool_executions
GROUP BY tool_name
ORDER BY count DESC;
```

### Option B: Python/Pandas

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('my_agent_data.db')

# Load recent invocations
invocations = pd.read_sql_query("""
    SELECT * FROM agent_invocations
    ORDER BY started_at DESC
    LIMIT 10
""", conn)

print(invocations)

# Token usage analysis
tokens = pd.read_sql_query("""
    SELECT model_name, SUM(total_tokens) as total_tokens,
           AVG(latency_ms) as avg_latency
    FROM llm_interactions
    GROUP BY model_name
""", conn)

print(tokens)
```

### Option C: Debug YAML Logs

View human-readable logs:
```bash
cat logs/adk_debug.yaml
```

## 5. Monitor in Real-Time

Watch the debug log as your agent runs:
```bash
tail -f logs/adk_debug.yaml
```

## Architecture Overview

```
┌─────────────────────────────────────┐
│    ADK Runner (app_factory.py)      │
└───────────┬─────────────────────────┘
            │
      ┌─────┴─────┐
      │           │
      ▼           ▼
┌─────────┐  ┌──────────┐
│ Session │  │ Plugins  │
│ Service │  │          │
└────┬────┘  └────┬─────┘
     │            │
     │      ┌─────┴──────┐
     │      │            │
     │      ▼            ▼
     │  ┌────────┐  ┌──────────┐
     │  │ Debug  │  │ Database │
     │  │ YAML   │  │ Telemetry│
     │  └────────┘  └────┬─────┘
     │                   │
     └───────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ my_agent_data.db   │
    │                    │
    │ • Sessions         │
    │ • Invocations      │
    │ • LLM Calls        │
    │ • Tool Executions  │
    │ • Session States   │
    └────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| [session_service.py](src/spendmend_adk/services/session_service.py) | ADK session storage config |
| [database_telemetry_plugin.py](src/spendmend_adk/services/database_telemetry_plugin.py) | Custom telemetry plugin |
| [telemetry_db.py](src/spendmend_adk/services/telemetry_db.py) | Database schema |
| [plugins.py](src/spendmend_adk/services/plugins.py) | Plugin configuration |
| [settings.py](src/spendmend_adk/settings.py) | App configuration |
| [DATABASE.md](DATABASE.md) | Full documentation |

## Troubleshooting

**Q: Tables not created?**
A: Run `python scripts/init_database.py`

**Q: No telemetry data?**
A: Check that `TELEMETRY_ENABLED=true` in `.env`

**Q: Debug log empty?**
A: Ensure `logs/` directory exists: `mkdir -p logs`

**Q: Database locked error?**
A: SQLite has limited concurrency. For production, use PostgreSQL.

## Next Steps

- Read [DATABASE.md](DATABASE.md) for detailed documentation
- Explore analytics queries in the database
- Consider setting up PostgreSQL for production
- Build dashboards using the telemetry data

## Cost Analysis Example

Calculate token costs:

```sql
SELECT
    model_name,
    SUM(prompt_tokens) as input_tokens,
    SUM(completion_tokens) as output_tokens,
    SUM(total_tokens) as total_tokens,
    -- Example pricing (adjust for your model):
    -- Gemini Flash: $0.15 per 1M input, $0.60 per 1M output
    (SUM(prompt_tokens) * 0.15 / 1000000) +
    (SUM(completion_tokens) * 0.60 / 1000000) as estimated_cost_usd
FROM llm_interactions
GROUP BY model_name;
```
