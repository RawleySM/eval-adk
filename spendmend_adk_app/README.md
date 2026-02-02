# Spendmend ADK App

A self-improving agent system built with Google's Agent Development Kit (ADK) for automating Spendmend development tasks.

## Overview

This application implements an autonomous agent that:
- Processes Jira tickets and implements solutions
- Compares its work against human baselines (merged PRs)
- Identifies gaps and areas for improvement
- Automatically updates itself with better tools, prompts, and schemas
- Continuously evaluates and improves its performance

## Architecture

### Key Components

1. **Focus Agent (spendmend_dev)**: The main developer agent that processes Jira tickets
2. **Baseline Fetcher**: Retrieves merged PRs as "human baseline" solutions
3. **Gap Reporter**: Compares agent output vs. human baseline
4. **Agent Updater**: Proposes improvements based on identified gaps
5. **Patch Writer**: Implements proposed changes to the focus agent
6. **Eval Runner**: Re-evaluates agent performance after updates
7. **Completion Checker**: Signals when all tickets are processed

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     Loop Agent                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Sequential Pipeline                      │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ 1. spendmend_dev: Process Jira ticket          │  │  │
│  │  │ 2. baseline_fetcher: Get human solution        │  │  │
│  │  │ 3. gap_reporter: Compare agent vs human        │  │  │
│  │  │ 4. agent_updater: Propose improvements         │  │  │
│  │  │ 5. patch_writer: Implement changes             │  │  │
│  │  │ 6. eval_runner: Re-evaluate performance        │  │  │
│  │  │ 7. completion_checker: Check if done           │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
spendmend_adk_app/
├── README.md
├── pyproject.toml
├── .env.example
├── src/spendmend_adk/
│   ├── __init__.py
│   ├── main.py                    # CLI entrypoint
│   ├── app_factory.py             # Runner builder
│   ├── settings.py                # Configuration
│   ├── services/                  # Service configurations
│   │   ├── session_service.py
│   │   ├── artifact_service.py
│   │   ├── context_cache.py
│   │   └── plugins.py
│   ├── tools/                     # Agent tools
│   │   ├── jira_tools.py
│   │   ├── github_tools.py
│   │   ├── databricks_sql_tools.py
│   │   ├── artifact_tools.py
│   │   └── fs_tools.py
│   ├── schemas/                   # Pydantic schemas
│   │   ├── common.py
│   │   ├── dev_task.py
│   │   ├── pr_baseline.py
│   │   ├── review.py
│   │   ├── update_plan.py
│   │   └── eval.py
│   ├── agents/
│   │   ├── workflow/
│   │   │   └── root_loop.py       # Workflow orchestration
│   │   ├── focus/
│   │   │   └── spendmend_dev/     # Focus agent
│   │   │       ├── agent.py
│   │   │       └── prompt.md
│   │   └── builders/              # Builder agents
│   │       ├── baseline_fetcher/
│   │       ├── gap_reporter/
│   │       ├── agent_updater/
│   │       ├── patch_writer/
│   │       └── eval_runner/
│   └── eval/
│       └── datasets/              # Evaluation datasets
└── artifacts/                     # Runtime artifact storage
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to:
  - Jira instance
  - GitHub repositories
  - Databricks SQL warehouse
  - Google Gemini API

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/spendmend/spendmend-adk.git
   cd spendmend-adk
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. Initialize database:
   ```bash
   # The database will be automatically created on first run
   # Default: sqlite (./my_agent_data.db)
   ```

## Usage

### Running the Agent

```bash
python -m spendmend_adk.main
```

Or using the CLI entry point:

```bash
spendmend-agent
```

### Configuration

All configuration is done via environment variables (see `.env.example`).

Key settings:
- `DATABASE_URL`: Session storage database
- `ARTIFACT_ROOT_DIR`: Where to store artifacts
- `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`: Jira credentials
- `GITHUB_TOKEN`: GitHub access token
- `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`: Databricks credentials
- `GEMINI_API_KEY`: Google Gemini API key

### Processing Tickets

Edit `src/spendmend_adk/main.py` to specify ticket keys:

```python
ticket_keys = [
    "SPEND-101",
    "SPEND-102",
]
```

Then run the application. The agent will:
1. Process each ticket
2. Compare against human baseline
3. Identify gaps
4. Improve itself
5. Re-evaluate
6. Move to next ticket

## Architecture Details

### Session Management

Uses `DatabaseSessionService` with SQLite (async) by default:
- Stores session state, conversation history, and agent outputs
- Session-scoped for multi-user support
- Can be configured to use PostgreSQL or other databases

### Artifact Storage

Uses `FileArtifactService` for filesystem-backed storage:
- Stores patches, reports, logs, and other artifacts
- Supports versioning (revision numbers)
- Session-scoped organization
- Located in `./artifacts/` by default

### Context Caching

Implements `ContextCacheConfig` for efficiency:
- Caches common contexts between agent invocations
- Reduces API costs and latency
- Configurable TTL and max entries
- Particularly useful for repeated prompts/instructions

### Structured I/O

All agents use Pydantic schemas for structured input/output:
- `input_schema`: Validates agent input
- `output_schema`: Validates agent output
- `output_key`: Stores output in session state for downstream agents

Example:
```python
spendmend_dev = LlmAgent(
    name="spendmend_dev",
    input_schema=SpendmendDevInput,
    output_schema=SpendmendDevOutput,
    output_key="spendmend_dev.output_json",
)
```

Downstream agents access outputs via:
```python
session.state["spendmend_dev.output_json"]
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Type Checking

```bash
mypy src/
```

## TODO

### Implementation Tasks

- [ ] Implement all tool functions (currently skeletons with `pass`)
- [ ] Add actual Jira API integration
- [ ] Add actual GitHub API integration
- [ ] Add actual Databricks SQL integration
- [ ] Implement artifact service read/write logic
- [ ] Add proper error handling and retries
- [ ] Add logging throughout the application

### Feature Enhancements

- [ ] Add CLI with argparse/click for ticket selection
- [ ] Add resume capability for interrupted sessions
- [ ] Add metrics dashboard/reporting
- [ ] Add cost tracking for API calls
- [ ] Add support for multiple focus agents
- [ ] Add web UI for monitoring progress

### Testing

- [ ] Add unit tests for schemas
- [ ] Add integration tests for agents
- [ ] Add end-to-end workflow tests
- [ ] Add mock services for testing without credentials

### Documentation

- [ ] Add detailed API documentation
- [ ] Add agent prompt engineering guide
- [ ] Add troubleshooting guide
- [ ] Add architecture decision records (ADRs)

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Contact

For questions or support, contact:
- Rawley Fowler: rawley@spendmend.com
- GitHub Issues: https://github.com/spendmend/spendmend-adk/issues
