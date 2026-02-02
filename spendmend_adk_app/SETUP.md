# Setup Guide

This guide will help you set up and start using the Spendmend ADK App.

## Quick Start

### 1. Install Dependencies

```bash
cd spendmend_adk_app
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:
- Jira URL, email, and API token
- GitHub personal access token
- Databricks host, token, and warehouse ID
- Google Gemini API key

### 3. Verify Installation

```bash
python -c "import spendmend_adk; print('Installation successful!')"
```

### 4. Run the Application

```bash
python -m spendmend_adk.main
```

Or:
```bash
spendmend-agent
```

## Detailed Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Git
- Access to:
  - Jira instance
  - GitHub repositories
  - Databricks SQL warehouse
  - Google Gemini API

### Obtaining Credentials

#### Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name (e.g., "Spendmend Agent")
4. Copy the token and save it in `.env` as `JIRA_API_TOKEN`

#### GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`
4. Generate token and save it in `.env` as `GITHUB_TOKEN`

#### Databricks Personal Access Token

1. In your Databricks workspace, go to Settings > User Settings
2. Go to Access Tokens tab
3. Click "Generate New Token"
4. Copy the token and save it in `.env` as `DATABRICKS_TOKEN`

#### Databricks SQL Warehouse ID

1. In your Databricks workspace, go to SQL Warehouses
2. Select your warehouse
3. Copy the warehouse ID from the URL or details panel
4. Save it in `.env` as `DATABRICKS_WAREHOUSE_ID`

#### Google Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Create a new API key or use an existing one
3. Save it in `.env` as `GEMINI_API_KEY`

### Database Setup

By default, the application uses SQLite with an async driver:
```
DATABASE_URL=sqlite+aiosqlite:///./my_agent_data.db
```

The database will be automatically created on first run.

For production, consider PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/spendmend_agents
```

### Directory Structure

The application will create these directories at runtime:
- `artifacts/`: Stores patches, reports, and logs
- `workspace/`: Local workspace for repository operations
- `my_agent_data.db`: SQLite database (if using default config)

## Customization

### Modifying Ticket List

Edit `src/spendmend_adk/main.py`:

```python
ticket_keys = [
    "SPEND-101",
    "SPEND-102",
    # Add your tickets here
]
```

### Adjusting Context Cache

In `.env`:
```
CONTEXT_CACHE_ENABLED=true
CONTEXT_CACHE_TTL_SECONDS=3600    # 1 hour
CONTEXT_CACHE_MAX_ENTRIES=256
```

### Changing Models

Edit agent definitions in `src/spendmend_adk/agents/*/agent.py`:

```python
spendmend_dev = LlmAgent(
    name="spendmend_dev",
    model="gemini-2.5-flash",  # Change this
    # ...
)
```

Available models:
- `gemini-2.5-flash`: Fast, cost-effective (default)
- `gemini-2.5-pro`: More capable, higher cost
- `gemini-1.5-pro`: Previous generation

## Troubleshooting

### Import Errors

If you see import errors:
```bash
pip install -e .
```

Ensure you're in the `spendmend_adk_app` directory.

### Database Errors

If you see database-related errors:
1. Delete `my_agent_data.db`
2. Restart the application

For SQLite connection issues, try switching to PostgreSQL.

### API Authentication Errors

Verify your credentials in `.env`:
- Ensure no extra spaces
- Ensure tokens are valid and not expired
- Check API permissions/scopes

### Tool Execution Errors

Most tools have skeleton implementations with `pass` statements. To make them functional:
1. Implement the tool function in `src/spendmend_adk/tools/`
2. Add proper error handling
3. Test the tool independently before running the full workflow

## Next Steps

1. **Implement Tools**: Fill in the tool skeletons in `src/spendmend_adk/tools/`
2. **Test Components**: Write unit tests for schemas, tools, and agents
3. **Customize Prompts**: Adjust agent prompts in `*/prompt.md` files
4. **Add Monitoring**: Set up logging and metrics collection
5. **Scale Up**: Move to production-grade database and artifact storage

## Support

For issues or questions:
- Check the README.md for detailed documentation
- Review the source code comments
- Open an issue on GitHub
