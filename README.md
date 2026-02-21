# pan

Multi-agent system for home and life operations. Built with Python, LangGraph, and Discord — deployed via Docker.

Pan runs a team of specialized AI agents that handle different domains of household management. A supervisor routes incoming messages to the right agent, each agent has its own tools and personality, and the whole system is accessible through a Discord bot.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Discord Bot                           │
│               /ask  /status  approval UI                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                     Message Router                            │
│          route_message() → stream graph events                │
│          resume_after_approval() → human-in-loop              │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   Supervisor (LangGraph)                      │
│       LLM-powered router with structured output               │
│       Decides which domain agent handles the request           │
│       Supports direct routing via /ask <domain>               │
└────────┬─────────────┬───────────────────────────────────────┘
         │             │
         ▼             ▼
┌──────────────────────┐ ┌──────────────┐  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│     Tech Chair       │ │House Manager │    Future agents:
│                      │ │              │  │ Treasurer          │
│ • Portainer (multi)  │ │ • Rent status│    Media Expert
│ • Proxmox VE (VMs)  │ │ • Tenants    │  │ Social Chair       │
│ • TrueNAS (storage)  │ │ • Payments   │    Professional Rels
│ • UniFi (network)    │ │ • Plaid/Zelle│  │ Public Relations   │
│                      │ │ • Late fees  │    House Doctor
│  24 tools            │ │ • Leases     │  └ ─ ─ ─ ─ ─ ─ ─ ─ ┘
│                      │ │  7 tools     │
└──────────────────────┘ └──────────────┘

┌──────────────────────────────────────────────────────────────┐
│                        Services                               │
│                                                               │
│   PostgreSQL ─── SQLAlchemy async ─── Alembic migrations      │
│   Redis ──────── caching / pub-sub                            │
│   LangGraph ──── checkpointer (psycopg3)                      │
│   APScheduler ── cron jobs (rent check, Plaid sync, matching) │
│   Plaid ──────── bank transaction sync (Zelle detection)      │
│   FastAPI ────── Admin API (port 8080)                        │
│   OpenRouter ─── LLM API (Claude Sonnet)                      │
└──────────────────────────────────────────────────────────────┘
```

### Key design decisions

- **Supervisor pattern**: A central LangGraph `StateGraph` routes messages to domain agents. Each agent is a LangGraph `react_agent` with its own tools, prompt, and model config. After an agent responds, control returns to the supervisor.
- **Approval workflow**: Agents can trigger human-in-the-loop interrupts. The Discord bot presents approve/reject buttons and pauses the graph until an admin responds (or times out after 5 minutes).
- **Persistence**: LangGraph state is checkpointed to Postgres via `AsyncPostgresSaver`, so conversations survive restarts. Each Discord thread gets its own `thread_id` for multi-turn context.
- **Scheduled tasks**: APScheduler runs cron jobs — monthly rent checks (1st at 9 AM), Plaid transaction sync (every 6 hours), and automated payment matching (every 6h15m).
- **Payment reconciliation**: Plaid pulls bank transactions, detects Zelle payments via `original_description` parsing, and fuzzy-matches sender names against tenants using rapidfuzz.
- **Admin API + UI**: FastAPI serves a REST API on port 8080 for tenant/unit/payment CRUD. A React admin UI on port 5173 provides a dashboard for managing tenants, viewing transactions, uploading leases, and connecting bank accounts.
- **Config**: All settings use Pydantic `BaseSettings` with `PAN_` env prefix and `__` nesting (`PAN_DB__HOST`, `PAN_DISCORD__TOKEN`, etc.).

### Agents

| Agent | Domain | Integrations | Tools |
|-------|--------|--------------|-------|
| **Tech Chair** | Infrastructure | Portainer (multi-instance), Proxmox VE, TrueNAS Scale, UniFi | 24 tools — containers, VMs, storage, network |
| **House Manager** | Tenant & rent | PostgreSQL, Plaid (Zelle/bank transactions) | 7 tools — rent status, tenants, payments, late fees, reminders, bank transactions, reconciliation |

Each agent is defined as a module under `src/pan/agents/<domain>/` with:
- `agent.py` — creates the LangGraph agent and registers tools
- `*_tools.py` — `@tool`-decorated async functions (one file per integration)
- System prompt in `src/pan/config/prompts/<domain>.txt`

## Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL, Redis (or use existing infrastructure)
- A Discord bot token
- An OpenRouter API key

### 1. Clone and install

```bash
git clone <repo-url> && cd pan
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Required variables:

```env
# Discord
PAN_DISCORD__TOKEN=your-discord-bot-token
PAN_DISCORD__GUILD_ID=123456789
PAN_DISCORD__ADMIN_USER_IDS=[123456789]

# LLM
PAN_OPENROUTER__API_KEY=your-openrouter-api-key

# Database
PAN_DB__HOST=localhost
PAN_DB__PORT=5432
PAN_DB__USER=pan
PAN_DB__PASSWORD=changeme
PAN_DB__NAME=pan

# Redis
PAN_REDIS__HOST=localhost
PAN_REDIS__PORT=6379

# Portainer (multi-instance)
PAN_PORTAINER__INSTANCES__MAIN__BASE_URL=https://portainer.local:9443
PAN_PORTAINER__INSTANCES__MAIN__API_KEY=your-api-key
PAN_PORTAINER__INSTANCES__GPU__BASE_URL=https://gpu-host:9443
PAN_PORTAINER__INSTANCES__GPU__API_KEY=your-gpu-api-key

# TrueNAS Scale
PAN_TRUENAS__BASE_URL=https://truenas.local/api/v2.0
PAN_TRUENAS__API_KEY=your-truenas-api-key

# Proxmox VE
PAN_PROXMOX__BASE_URL=https://proxmox.local:8006
PAN_PROXMOX__API_TOKEN=root@pam!pan=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PAN_PROXMOX__NODE_NAME=pve

# UniFi
PAN_UNIFI__BASE_URL=https://192.168.1.1
PAN_UNIFI__API_KEY=your-unifi-api-key

# Plaid (bank transactions for rent tracking)
PAN_PLAID__CLIENT_ID=your-plaid-client-id
PAN_PLAID__SECRET=your-plaid-secret
PAN_PLAID__ENVIRONMENT=development

# General
PAN_DEBUG=true
PAN_LOG_LEVEL=DEBUG
```

### 3. Service integrations

Each external service Pan connects to has its own setup guide:

| Service | Used By | Guide |
|---------|---------|-------|
| Discord | Interface — slash commands, approval UI | [docs/discord.md](docs/discord.md) |
| Portainer | Tech Chair — Docker container management (multi-instance) | [docs/portainer.md](docs/portainer.md) |
| Proxmox VE | Tech Chair — VM and LXC container management | [docs/proxmox.md](docs/proxmox.md) |
| TrueNAS Scale | Tech Chair — ZFS storage, disks, snapshots, alerts | [docs/truenas.md](docs/truenas.md) |
| UniFi | Tech Chair — Network devices, clients, WAN, networks | [docs/unifi.md](docs/unifi.md) |
| Plaid | House Manager — Bank transaction sync, Zelle payment detection | [docs/plaid.md](docs/plaid.md) |

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the application

**With Docker:**

```bash
docker compose up -d
```

**Locally (for development):**

```bash
# Ensure Postgres and Redis are accessible
python -m pan
```

### 6. Discord bot commands

| Command | Description |
|---------|-------------|
| `/ask <domain> <question>` | Ask a specific agent (or choose "Auto" for supervisor routing) |
| `/status` | Check active agents and bot latency |

## Development

### Linting & formatting

```bash
ruff check .          # lint
ruff check --fix .    # lint + auto-fix
ruff format .         # format
mypy src/             # type check
```

### Testing

```bash
pytest                                        # full suite
pytest tests/test_something.py                # single file
pytest -k "keyword"                           # keyword match
pytest --cov=src/pan --cov-report=term-missing  # with coverage
```

### Adding a new agent

1. Create `src/pan/agents/<domain>/` with `__init__.py`, `agent.py`, `tools.py`
2. Write the system prompt in `src/pan/config/prompts/<domain>.txt`
3. Optionally add a model config in `src/pan/config/models.py`
4. Register the agent in `src/pan/agents/registry.py` → `init_agents()`
5. Add a choice to the Discord `/ask` command in `src/pan/interface/discord_bot.py`

## Project structure

```
pan/
├── src/pan/
│   ├── __main__.py              # Entry point
│   ├── agents/
│   │   ├── base.py              # create_domain_agent() factory
│   │   ├── registry.py          # Agent registration + init
│   │   ├── tech_chair/          # Infra: Portainer, Proxmox, TrueNAS, UniFi
│   │   └── house_manager/       # Rent & tenant management
│   ├── orchestration/
│   │   ├── supervisor.py        # LangGraph supervisor graph
│   │   ├── router.py            # Message routing + approval resume
│   │   ├── scheduler.py         # APScheduler cron jobs
│   │   └── state.py             # AgentState (MessagesState + metadata)
│   ├── interface/
│   │   ├── discord_bot.py       # Discord bot + slash commands
│   │   └── discord_views.py     # Approval button UI
│   ├── services/
│   │   ├── database.py          # SQLAlchemy async engine + sessions
│   │   ├── models.py            # ORM models (User, Tenant, RentPayment, PlaidItem, BankTransaction, LeaseDocument)
│   │   ├── checkpointer.py      # LangGraph Postgres checkpointer
│   │   ├── redis.py             # Redis client
│   │   ├── plaid_service.py     # Plaid API: link, sync, Zelle detection
│   │   ├── payment_matcher.py   # Fuzzy tenant matching + reconciliation
│   │   └── notifications.py     # Discord channel notifications
│   ├── api/
│   │   ├── app.py               # FastAPI factory (port 8080)
│   │   └── routes/              # REST endpoints: tenants, units, payments, plaid, leases
│   ├── config/
│   │   ├── settings.py          # Pydantic BaseSettings
│   │   ├── models.py            # Per-agent LLM config
│   │   ├── logging.py           # structlog setup
│   │   └── prompts/             # Agent system prompts (.txt)
│   └── exceptions.py            # PanError hierarchy
├── admin/                       # React admin UI (Vite + TypeScript)
├── tests/
├── docs/                        # Integration setup guides
├── alembic/                     # Database migrations
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```
