# AGENTS.md — Coding Agent Instructions for `pan`

> Home Agent Framework — multi-agent system for home/life operations.
> Python + LangGraph, Docker-deployed, Discord/Telegram interface.

---

## Build / Run / Test Commands

### Environment Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# Install dependencies
pip install -e ".[dev]"
```

### Running

```bash
# Start all services (Postgres, Redis, Vector DB, MQTT)
docker compose up -d

# Run the main application
python -m pan

# Run a specific agent in isolation
python -m pan.agents.<domain>      # e.g. pan.agents.tech_chair
```

### Linting and Formatting

```bash
# Lint
ruff check .

# Lint and auto-fix
ruff check --fix .

# Format
ruff format .

# Type checking
mypy src/
```

### Testing

```bash
# Run full test suite
pytest

# Run a single test file
pytest tests/test_something.py

# Run a single test function
pytest tests/test_something.py::test_function_name

# Run tests matching a keyword
pytest -k "keyword"

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src/pan --cov-report=term-missing
```

---

## Project Structure

```
pan/
├── src/pan/
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   ├── agents/                  # Agent domain modules
│   │   ├── tech_chair/
│   │   ├── house_manager/
│   │   ├── treasurer/
│   │   ├── media_expert/
│   │   ├── professional_relations/
│   │   ├── public_relations/
│   │   ├── social_chair/
│   │   └── house_doctor/
│   ├── orchestration/           # Supervisor, scheduler, message router
│   ├── interface/               # Discord bot, Telegram bot
│   ├── mcp_servers/             # MCP server wrappers per integration
│   ├── services/                # Shared services (DB, Redis, Vector)
│   └── config/                  # Settings, model configs, prompts
├── tests/                       # Mirrors src/pan/ structure
├── docker-compose.yml
├── pyproject.toml
└── AGENTS.md
```

---

## Code Style Guidelines

### Python Version

- Target **Python 3.12+**. Use modern syntax: `type` statements, `match/case`,
  `X | Y` union types, f-strings everywhere.

### Formatting and Linting

- **Ruff** for both linting and formatting (replaces black, isort, flake8).
- Line length: **100 characters**.
- Use ruff's default rules plus: `I` (isort), `UP` (pyupgrade), `N` (pep8-naming),
  `ASYNC` (async checks), `S` (bandit/security), `B` (bugbear).

### Import Order

Ruff/isort handles this automatically. The order is:

1. Standard library
2. Third-party packages
3. Local/project imports

Separate each group with a blank line. Use absolute imports from `pan.*`.

```python
import asyncio
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from pan.services.database import get_session
from pan.agents.tech_chair.tools import list_containers
```

### Type Annotations

- **All** function signatures must have full type annotations (params + return).
- Use `from __future__ import annotations` only if needed for forward refs.
- Prefer built-in generics: `list[str]`, `dict[str, Any]`, `str | None`.
- Use `TypedDict` for structured state objects (LangGraph state pattern).
- Use `Pydantic BaseModel` for API request/response schemas and config.

```python
def get_agent_config(domain: str) -> AgentConfig:
    ...

class AgentState(TypedDict):
    messages: list[BaseMessage]
    next_agent: str | None
```

### Naming Conventions

| Element       | Convention          | Example                        |
|---------------|---------------------|--------------------------------|
| Modules       | `snake_case`        | `tech_chair`, `rent_checker`   |
| Classes       | `PascalCase`        | `AgentSupervisor`, `RentState` |
| Functions     | `snake_case`        | `check_rent_status`            |
| Constants     | `UPPER_SNAKE_CASE`  | `MAX_RETRIES`, `DEFAULT_MODEL` |
| Type aliases  | `PascalCase`        | `AgentResponse`                |
| Private       | Leading underscore  | `_internal_helper`             |
| Env vars      | `PAN_` prefix       | `PAN_DISCORD_TOKEN`            |

### Async Patterns

- All I/O-bound operations must be `async`. Agents, bots, and API calls are async.
- Use `asyncio` — do not use `threading` for I/O concurrency.
- Use `asyncio.TaskGroup` for concurrent operations where possible.
- Prefix async functions clearly when they wrap sync operations:
  `async def fetch_containers()` not `async def containers()`.

### Error Handling

- Use specific exception types, never bare `except:` or `except Exception:` at
  the top level without re-raising or logging.
- Create domain-specific exceptions in each agent module:
  `class ContainerNotFoundError(PanError)`.
- All agent tool functions should catch expected errors and return structured
  error responses rather than letting exceptions propagate to the LLM.
- Log errors with `structlog` (structured logging), include context fields.

```python
import structlog

logger = structlog.get_logger()

try:
    result = await portainer_client.get_container(container_id)
except ContainerNotFoundError:
    logger.warning("container_not_found", container_id=container_id)
    return ToolResponse(error=f"Container {container_id} not found")
```

### Configuration and Secrets

- **Never** hardcode credentials, tokens, or API keys in source code.
- Use environment variables with `PAN_` prefix, loaded via Pydantic `BaseSettings`.
- Store secrets via Docker secrets or `.env` file (`.env` must be in `.gitignore`).
- Each agent domain has its own config dataclass defining required settings.

### LangGraph / Agent Patterns

- Each agent domain is a LangGraph `StateGraph` with a typed state dict.
- Tools are defined as functions decorated with `@tool` from `langchain_core.tools`.
- System prompts live in `src/pan/config/prompts/` as plain text files, not inline strings.
- Model selection is per-agent, configured in `src/pan/config/models.py`.
- Approval-gated actions must route through the supervisor's approval workflow — agents
  must never execute restricted actions (social posts, job applications) directly.

### MCP Servers

- One MCP server per integration domain (proxmox, portainer, truenas, etc.).
- MCP servers may be Python or TypeScript — if TypeScript, follow standard
  Node.js conventions (ESM, strict TypeScript, biome for formatting).
- Each MCP server exposes tools via the MCP protocol and is a standalone
  Docker container or subprocess.

### Docker and Deployment

- Every service has a Dockerfile in its directory.
- `docker-compose.yml` at repo root orchestrates all services.
- Use multi-stage builds to keep images small.
- Health checks required for all services.

### Git Conventions

- Branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`.
- Commit messages: imperative mood, concise. e.g. `add rent checker cron job`.
- Keep commits atomic — one logical change per commit.

### Testing Conventions

- Use `pytest` with `pytest-asyncio` for async tests.
- Test files mirror source structure: `tests/agents/tech_chair/test_containers.py`.
- Use fixtures for database sessions, API clients, and mock services.
- Mock external APIs — never make real API calls in tests.
- Name tests descriptively: `test_rent_checker_sends_reminder_when_overdue`.
