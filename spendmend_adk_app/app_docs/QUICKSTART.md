# Quick Start Guide

Get up and running with the Spendmend ADK App in 5 minutes.

## 1. Install (1 minute)

```bash
cd spendmend_adk_app
pip install -e .
```

## 2. Verify Installation (30 seconds)

```bash
python verify_setup.py
```

You should see "✓ All checks passed!" (except for optional dependencies).

## 3. Configure Environment (2 minutes)

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required for basic functionality
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_jira_api_token

GITHUB_TOKEN=your_github_token

DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_token
DATABRICKS_WAREHOUSE_ID=your_warehouse_id

GEMINI_API_KEY=your_gemini_api_key
```

See [SETUP.md](SETUP.md) for detailed instructions on obtaining credentials.

## 4. Test Import (30 seconds)

```bash
python -c "import spendmend_adk; print('✓ Import successful!')"
```

## 5. Implement Your First Tool (Optional)

Before running the full workflow, implement at least one tool. For example, in `src/spendmend_adk/tools/jira_tools.py`:

```python
def jira_get_issue(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """Get detailed information about a specific Jira issue."""
    from jira import JIRA

    # Get credentials from settings
    from spendmend_adk.settings import settings

    jira = JIRA(
        server=settings.jira_url,
        basic_auth=(settings.jira_email, settings.jira_api_token)
    )

    issue = jira.issue(args["issue_key"])

    return {
        "ok": True,
        "issue": {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description,
            "status": str(issue.fields.status),
            "assignee": str(issue.fields.assignee),
        }
    }
```

## 6. Run (30 seconds)

```bash
python -m spendmend_adk.main
```

Or:

```bash
spendmend-agent
```

## What Happens Next?

The agent will:
1. Process each ticket in the list (see `main.py`)
2. Compare its work against human baselines
3. Identify gaps and improve itself
4. Re-evaluate and continue

## Common Issues

### "ModuleNotFoundError: No module named 'google.adk'"

Google ADK might not be published yet. You can:
- Wait for official release
- Contact Google for pre-release access
- Mock the ADK interfaces for testing

### "ImportError: cannot import name..."

Run: `pip install -e .` from the project root.

### Tool functions return None

Tools have skeleton implementations with `pass` statements. Implement them as needed.

### Database errors

Delete `my_agent_data.db` and restart. The database will be recreated.

## Next Steps

1. **Implement Tools**: Fill in tool bodies in `src/spendmend_adk/tools/`
2. **Add Test Data**: Edit ticket list in `main.py`
3. **Customize Prompts**: Adjust agent prompts in `*/prompt.md`
4. **Add Logging**: Implement logging for debugging
5. **Write Tests**: Create test suite for your implementations

## Getting Help

- Read [README.md](README.md) for comprehensive documentation
- Check [SETUP.md](SETUP.md) for detailed setup instructions
- Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for architecture details
- Open an issue on GitHub for bugs/questions

## Development Workflow

```bash
# 1. Make changes to code
vim src/spendmend_adk/tools/jira_tools.py

# 2. Run verification
python verify_setup.py

# 3. Test your changes
python -m pytest tests/  # (when tests exist)

# 4. Format code
black src/
ruff check src/

# 5. Run the application
python -m spendmend_adk.main
```

## Architecture Quick Reference

```
User Request
    ↓
Loop Agent (orchestrates iterations)
    ↓
Sequential Pipeline:
    1. spendmend_dev      → Processes ticket, writes code
    2. baseline_fetcher   → Gets human solution (merged PR)
    3. gap_reporter       → Compares agent vs human
    4. agent_updater      → Proposes improvements
    5. patch_writer       → Implements changes
    6. eval_runner        → Re-evaluates performance
    7. completion_checker → Checks if done (escalate to stop loop)
    ↓
Loop continues until all tickets processed
```

## Key Files to Know

- `main.py`: Entry point - edit ticket list here
- `settings.py`: Configuration - loads from .env
- `app_factory.py`: Assembles all components
- `agents/workflow/root_loop.py`: Defines the workflow
- `agents/focus/spendmend_dev/`: The main developer agent
- `tools/*.py`: Tool implementations (IMPLEMENT THESE)
- `schemas/*.py`: Data models (already complete)

## Performance Expectations

- **Setup Time**: 5 minutes
- **First Run**: May take 2-4 minutes per ticket
- **Subsequent Runs**: Faster due to context caching
- **API Costs**: ~$0.10-0.50 per ticket (Gemini 2.5 Flash)

## Success Criteria

You'll know it's working when:
1. ✓ No import errors
2. ✓ Database is created (`my_agent_data.db`)
3. ✓ Artifacts directory is created
4. ✓ Agent produces JSON outputs in session state
5. ✓ Loop continues until completion_checker signals done

Happy building!
