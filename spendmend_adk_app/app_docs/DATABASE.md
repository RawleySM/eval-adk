# Database Configuration for ADK Sessions and Telemetry

This document describes the database setup for storing ADK agent sessions and telemetry data.

## Overview

The application uses a **single SQLite database** for both:
1. **Session Storage** - Managed by `DatabaseSessionService` from the ADK
2. **Telemetry Storage** - Managed by custom `DatabaseTelemetryPlugin`

This unified approach simplifies deployment and enables correlated analysis of agent behavior and performance.

## Database Location

Default location: `./my_agent_data.db`

Configure via environment variable:
```bash
export DATABASE_URL="sqlite+aiosqlite:///./my_agent_data.db"
```

## Database Schema

### Session Tables (ADK Built-in)
These tables are automatically created by `DatabaseSessionService`:
- Session metadata and state
- Conversation history
- User context

### Telemetry Tables (Custom)

#### `agent_invocations`
Tracks each agent invocation:
- `id` - Primary key
- `invocation_id` - Unique invocation identifier
- `session_id` - Links to session service
- `user_id` - User identifier
- `agent_name` - Name of the agent
- `started_at` - Start timestamp
- `completed_at` - Completion timestamp
- `status` - success, error, timeout
- `error_message` - Error details if failed

#### `llm_interactions`
Records all LLM API calls:
- `id` - Primary key
- `invocation_id` - Links to agent_invocations
- `timestamp` - When the call was made
- `model_name` - LLM model used (e.g., gemini-2.0-flash)
- `prompt_tokens` - Input tokens consumed
- `completion_tokens` - Output tokens generated
- `total_tokens` - Total tokens (prompt + completion)
- `latency_ms` - Response time in milliseconds
- `request_data` - JSON request parameters
- `response_data` - JSON response content
- `error_message` - Error details if failed

#### `tool_executions`
Records all tool/function calls:
- `id` - Primary key
- `invocation_id` - Links to agent_invocations
- `timestamp` - When the tool was called
- `tool_name` - Name of the tool executed
- `arguments` - JSON tool arguments
- `result` - JSON tool result
- `error_message` - Error details if failed
- `execution_time_ms` - Execution time

#### `session_states`
Snapshots of session state:
- `id` - Primary key
- `invocation_id` - Links to agent_invocations
- `timestamp` - When snapshot was taken
- `state_data` - JSON session state

## Initialization

### Option 1: Automatic Initialization
The telemetry tables are automatically created when the `DatabaseTelemetryPlugin` starts.

### Option 2: Manual Initialization
Run the initialization script:
```bash
cd spendmend_adk_app
python scripts/init_database.py
```

This will create all telemetry tables and provide helpful information about the database.

## Configuration

### Environment Variables

Configure in `.env` file or export directly:

```bash
# Database Configuration
DATABASE_URL="sqlite+aiosqlite:///./my_agent_data.db"

# Debug Logging
DEBUG_LOG_PATH="./logs/adk_debug.yaml"
TELEMETRY_ENABLED=true
```

### Settings File

Configuration is managed in [src/spendmend_adk/settings.py](src/spendmend_adk/settings.py):

```python
class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./my_agent_data.db"

    # Telemetry & Logging
    debug_log_path: str = "./logs/adk_debug.yaml"
    telemetry_enabled: bool = True
```

## Querying Telemetry Data

### Using SQLite CLI

```bash
# Open database
sqlite3 my_agent_data.db

# View recent invocations
SELECT invocation_id, agent_name, started_at, status
FROM agent_invocations
ORDER BY started_at DESC
LIMIT 10;

# Token usage by model
SELECT
    model_name,
    COUNT(*) as calls,
    SUM(total_tokens) as total_tokens,
    AVG(latency_ms) as avg_latency_ms
FROM llm_interactions
GROUP BY model_name;

# Most used tools
SELECT
    tool_name,
    COUNT(*) as executions,
    AVG(execution_time_ms) as avg_time_ms
FROM tool_executions
GROUP BY tool_name
ORDER BY executions DESC;

# Invocations with errors
SELECT
    invocation_id,
    agent_name,
    started_at,
    error_message
FROM agent_invocations
WHERE status = 'error'
ORDER BY started_at DESC;
```

### Using Python

```python
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('my_agent_data.db')

# Load data into pandas
invocations = pd.read_sql_query(
    "SELECT * FROM agent_invocations",
    conn
)

llm_calls = pd.read_sql_query(
    "SELECT * FROM llm_interactions",
    conn
)

# Analyze token usage
token_summary = llm_calls.groupby('model_name').agg({
    'total_tokens': ['sum', 'mean'],
    'latency_ms': 'mean',
    'invocation_id': 'count'
})

print(token_summary)
```

## Production Considerations

### SQLite Limitations
SQLite is suitable for:
- Development and testing
- Single-server deployments
- Low to moderate traffic

For production at scale, consider:
- **PostgreSQL**: `postgresql+asyncpg://user:pass@host/dbname`
- **MySQL**: `mysql+aiomysql://user:pass@host/dbname`

### Database URL Examples

```bash
# SQLite (current)
DATABASE_URL="sqlite+aiosqlite:///./my_agent_data.db"

# PostgreSQL on Cloud SQL
DATABASE_URL="postgresql+asyncpg://user:pass@cloudsql-proxy:5432/agent_db"

# PostgreSQL local
DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/agent_db"
```

### Backup and Maintenance

For SQLite:
```bash
# Backup database
cp my_agent_data.db my_agent_data.backup.$(date +%Y%m%d).db

# Vacuum to optimize
sqlite3 my_agent_data.db "VACUUM;"
```

## Monitoring and Analytics

### Key Metrics to Track

1. **Cost Tracking**: Sum of `total_tokens` by `model_name`
2. **Performance**: Average `latency_ms` for LLM calls
3. **Reliability**: Count of invocations by `status`
4. **Tool Usage**: Frequency and execution time of tools

### Example Dashboard Queries

```sql
-- Daily token usage
SELECT
    DATE(timestamp) as date,
    model_name,
    SUM(total_tokens) as tokens
FROM llm_interactions
GROUP BY date, model_name
ORDER BY date DESC;

-- Agent performance
SELECT
    agent_name,
    COUNT(*) as invocations,
    AVG(JULIANDAY(completed_at) - JULIANDAY(started_at)) * 86400 as avg_duration_sec,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
FROM agent_invocations
GROUP BY agent_name;
```

## Troubleshooting

### Database locked error
SQLite has limited concurrent write support. For production, use PostgreSQL.

### Tables not created
Ensure the `DatabaseTelemetryPlugin` is initialized:
```python
python scripts/init_database.py
```

### Missing data
Check that:
1. `telemetry_enabled = True` in settings
2. Plugins are configured in `app_factory.py`
3. No exceptions in the telemetry plugin

### Large database file
- SQLite files can grow large with extensive logging
- Consider rotating old data or archiving
- Set appropriate `max_response_length` in plugin config

## Related Files

- [settings.py](src/spendmend_adk/settings.py) - Configuration
- [session_service.py](src/spendmend_adk/services/session_service.py) - Session service
- [database_telemetry_plugin.py](src/spendmend_adk/services/database_telemetry_plugin.py) - Telemetry plugin
- [telemetry_db.py](src/spendmend_adk/services/telemetry_db.py) - Database schema
- [plugins.py](src/spendmend_adk/services/plugins.py) - Plugin configuration
- [app_factory.py](src/spendmend_adk/app_factory.py) - Application assembly

## References

- [ADK DatabaseSessionService Documentation](https://google.github.io/adk-docs/sessions/session/#databasesessionservice)
- [ADK Plugins Documentation](https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.plugins)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
