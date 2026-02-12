# Home Agent Framework — Master Plan

## Table of Contents

1. [Agent Inventory](#1-agent-inventory)
2. [External Connections & Integrations](#2-external-connections--integrations)
3. [Architecture](#3-architecture)
4. [Execution Modes](#4-execution-modes)
5. [Agent Prioritization & Build Order](#5-agent-prioritization--build-order)
6. [Tech Stack Summary](#6-tech-stack-summary)
7. [Key Risks & Callouts](#7-key-risks--callouts)
8. [Timeline Estimates](#8-timeline-estimates)

---

## 1. Agent Inventory

### 1. Professional Relations
1. Resume editor
2. Application filler
3. Networker
4. Event planner/scheduler

### 2. Tech Chair
1. Manage containers
2. Manage hypervisor
3. Manage network
4. Manage NAS
5. Suggest and execute migrations
6. Document architecture

### 3. House Manager
1. Rent checker/notifier/late fee czar
2. Maintenance/construction scheduler
3. Suspicious footage reviewer

### 4. Social Chair
1. Event planner/scheduler
2. Party idea generator
3. Travel planner
4. Wedding planner

### 5. Treasurer
1. Financial planning
2. Accounting
3. Budgeting

### 6. Public Relations
1. Social media management
2. Brand management
3. Suggested posts

### 7. House Doctor
1. Physical trainer
2. Dietician
3. Physician (health/sleep tracker data)
4. Light duty therapist/psych

### 8. Media Expert
1. Answer any questions about playing or stored media
2. Retrieve clips
3. Recommend new media
4. Any in/any out

---

## 2. External Connections & Integrations

### Infrastructure APIs (local systems)

| Integration | Used By | Auth Method | Notes |
|---|---|---|---|
| **Proxmox API** | Tech Chair | API token | Manage VMs, monitor resources |
| **Portainer API** | Tech Chair | API key | Manage containers across both compute nodes |
| **TrueNAS API** | Tech Chair | API key | Monitor storage, manage shares/snapshots |
| **UniFi Controller API** | Tech Chair | Local account | Network management, client tracking |
| **Frigate API + MQTT** | House Manager (surveillance) | Local, MQTT broker | Event-driven clip retrieval, object detection results |
| **Home Assistant API** | House Manager, House Doctor | Long-lived access token | Smart home control, sensor data, automations |
| **Plex API** | Media Expert | Plex token | Library queries, playback, recommendations |
| **Jellyfin API** | Media Expert | API key | Same as Plex, alternative access |
| **Sonarr/Radarr/Lidarr APIs** | Media Expert | API keys | Search, request, monitor media |
| **Immich API** | Public Relations, Media Expert | API key | Photo search, album access, asset metadata |

### External Service APIs

| Integration | Used By | Auth Method | Complexity |
|---|---|---|---|
| **OpenRouter API** | ALL agents (LLM backbone) | API key | Low — single key, model routing built-in |
| **Discord Bot API** | Interface layer | Bot token | Medium — bot, slash commands, channel routing |
| **Telegram Bot API** | Interface layer | Bot token | Low — BotFather, simple webhook |
| **WhatsApp Business API** | Interface layer (future) | Meta Business verification | High — requires business verification, costly |
| **Gmail API (OAuth2)** | Professional Relations | OAuth2 client credentials | Medium — Google Cloud project, consent screen |
| **LinkedIn API** | Professional Relations, PR | OAuth2 | High — limited API access, may need scraping fallback |
| **Indeed/job board scrapers** | Professional Relations | Scraping/unofficial | Medium — fragile, needs maintenance |
| **Plaid API** | Treasurer | API key + tokens per institution | Medium — free dev tier, paid production |
| **Monarch Money** | Treasurer (transitional) | Unofficial/scraping | High — no public API, use as bridge while building Plaid |
| **Twitter/X API** | Public Relations | OAuth2 / API key | Medium — API costs $100/mo for basic posting access |
| **Instagram Graph API** | Public Relations | Meta Business, OAuth2 | High — requires Facebook Business page linkage |
| **MQTT Broker** | Tech Chair, House Manager | Local (Mosquitto) | Low — likely already running for Frigate/HA |

### Data Sources (no formal API, file/DB access)

| Source | Used By | Access Method |
|---|---|---|
| Resume files (PDF/DOCX) | Professional Relations | Local filesystem / NAS |
| Lease agreements | House Manager | NAS / structured DB |
| Tenant contact info | House Manager | PostgreSQL (custom schema) |
| Health/sleep data | House Doctor | Manual import initially, wearable API later |
| Financial records | Treasurer | Plaid + local PostgreSQL |

---

## 3. Architecture

```
+---------------------------------------------------------------+
|                      INTERFACE LAYER                           |
|  +----------+  +----------+  +----------+                     |
|  | Discord  |  | Telegram |  | WhatsApp |  (future)           |
|  |   Bot    |  |   Bot    |  |   Bot    |                     |
|  +----+-----+  +----+-----+  +----+-----+                     |
|       +──────────────+──────────────+                          |
|                      v                                         |
|            +──────────────────+                                |
|            |  Message Router  |  Routes by channel/command     |
|            +────────+─────────+  to the correct agent domain   |
+─────────────────────+─────────────────────────────────────────+
                      v
+---------------------------------------------------------------+
|                   ORCHESTRATION LAYER                          |
|                                                                |
|  +────────────────────────────────────────────────────+       |
|  |              Agent Supervisor                       |       |
|  |  - Receives routed messages                         |       |
|  |  - Dispatches to domain agents                      |       |
|  |  - Manages approval workflows (post approval, etc.) |       |
|  |  - Enforces rate limits & budgets                   |       |
|  +────────────────────+───────────────────────────────+       |
|                       |                                        |
|  +────────────────────v───────────────────────────────+       |
|  |              Scheduler (cron + event)               |       |
|  |  - Periodic tasks (rent check, health summary)      |       |
|  |  - Event-driven triggers (Frigate motion, new email)|       |
|  |  - On-demand via message interface                  |       |
|  +────────────────────────────────────────────────────+       |
+─────────────────────+─────────────────────────────────────────+
                      v
+---------------------------------------------------------------+
|                     AGENT LAYER                                |
|                                                                |
|  Each agent is a self-contained module with:                   |
|  - System prompt + persona                                     |
|  - Tool definitions (MCP or function-calling)                  |
|  - Model config (which OpenRouter model to use)                |
|  - Memory store (conversation history + domain knowledge)      |
|                                                                |
|  +──────────+ +──────────+ +──────────+ +──────────+          |
|  |Prof.Rel. | |Tech Chair| |House Mgr | |Social Ch.|          |
|  +──────────+ +──────────+ +──────────+ +──────────+          |
|  |Treasurer | |Pub.Rel.  | |House Doc | |Media Exp.|          |
|  +──────────+ +──────────+ +──────────+ +──────────+          |
+─────────────────────+─────────────────────────────────────────+
                      v
+---------------------------------------------------------------+
|                   TOOL / SERVICE LAYER                         |
|                                                                |
|  +─────────────────────────────────────────────────────+      |
|  |  MCP Servers (one per integration domain)            |      |
|  |  - proxmox-mcp    - truenas-mcp   - unifi-mcp      |      |
|  |  - frigate-mcp    - homeassistant-mcp               |      |
|  |  - plex-mcp       - jellyfin-mcp  - arr-mcp        |      |
|  |  - immich-mcp     - gmail-mcp     - linkedin-mcp   |      |
|  |  - plaid-mcp      - twitter-mcp   - instagram-mcp  |      |
|  |  - portainer-mcp  - filesystem-mcp                  |      |
|  +─────────────────────────────────────────────────────+      |
|                                                                |
|  +─────────────────────────────────────────────────────+      |
|  |  Shared Services                                     |      |
|  |  - Vector DB (ChromaDB/Qdrant) -- agent memory/RAG  |      |
|  |  - PostgreSQL -- structured data (tenants, finances) |      |
|  |  - Redis -- message queue, caching, rate limiting    |      |
|  |  - MQTT Broker -- event bus for real-time triggers   |      |
|  +─────────────────────────────────────────────────────+      |
+---------------------------------------------------------------+
```

### Key Architecture Decisions

**Language/Framework**: Python with LangGraph for complex multi-step workflows with approval gates (needed for post approvals, job applications, etc.). Alternative: CrewAI or raw OpenAI-compatible function calling for lighter agents.

**Why MCP servers**: Each integration gets wrapped as an MCP server. This means any agent can use any tool without tight coupling. You write the Proxmox MCP server once, and both the Tech Chair agent and the House Manager agent can call it.

**Deployment**: Each component runs as a Docker container managed through the existing Portainer setup on the compute nodes. The orchestration layer and agents run on the CPU node; anything needing GPU (vision analysis of Frigate clips) routes to the GPU node.

**Approval Workflow**: Critical for PR agents and Professional Relations. The supervisor holds actions that require approval (social media posts, job applications) in a queue and sends a Discord/Telegram message with approve/reject buttons.

---

## 4. Execution Modes

| Mode | Trigger | Examples |
|---|---|---|
| **Continuous/Streaming** | MQTT events, webhooks | Frigate motion events, new Gmail, Discord messages |
| **Periodic (cron)** | Scheduled intervals | Rent check (1st of month), health summaries (daily), financial reports (weekly), architecture docs (weekly) |
| **On-demand** | User message via chat | "Plan a party for 20 people", "Update my resume", "What movie should I watch?" |
| **Approval-gated** | Agent proposes, human confirms | Social media posts, job applications, container migrations, maintenance scheduling |

---

## 5. Agent Prioritization & Build Order

Scored on **Criticality** (how much value/risk), **Complexity** (how hard to build), and **Dependencies** (what must exist first). Ordered by recommended build sequence.

### Phase 0: Foundation (build first, everything depends on this)

| Component | Complexity | Notes |
|---|---|---|
| Message Router + Discord/Telegram bots | Medium | The entire interface layer. Without this, no agent is usable. |
| Agent Supervisor + Scheduler | Medium | Orchestration core. Approval workflows live here. |
| PostgreSQL + Redis + Vector DB | Low | `docker compose up` — straightforward infra |
| OpenRouter integration wrapper | Low | Thin client with model selection per agent config |

### Phase 1: High Value, Lower Complexity — "Quick Wins"

| # | Agent | Criticality | Complexity | Why First |
|---|---|---|---|---|
| 1 | **Tech Chair: Manage Containers** | **Critical** | Low | Already have Portainer. Wrapping its API as an MCP server is straightforward. Lets you manage your own agent infra via agents. Meta-bootstrapping. |
| 2 | **House Manager: Rent Checker** | **Critical** | Low | Direct money impact. Simple DB + cron. Check if rent is received, send reminders, calculate late fees per lease terms. |
| 3 | **Media Expert: Q&A + Recommendations** | High | Low-Med | Plex/Jellyfin APIs are well-documented. High daily-use value. Wire up library search + viewing history for recommendations. |
| 4 | **Tech Chair: Manage Network** | High | Medium | UniFi API is solid. Monitor clients, get alerts on anomalies, manage firewall rules via chat. |

### Phase 2: High Value, Medium Complexity

| # | Agent | Criticality | Complexity | Notes |
|---|---|---|---|---|
| 5 | **Treasurer: Budgeting + Accounting** | **Critical** | Medium-High | Start with Plaid integration for transaction ingestion. Build categorization, monthly summaries, budget tracking. Replace Monarch over time. |
| 6 | **House Manager: Suspicious Footage** | High | Medium | Frigate already does detection. This agent reviews Frigate events, classifies severity, alerts with clips on Discord. Vision model via OpenRouter. |
| 7 | **Professional Relations: Resume + Applications** | High | Medium | Gmail API for recruiter emails. Parse job descriptions, tailor resume, pre-fill applications. Approval-gated for fiancee's workflow. |
| 8 | **Tech Chair: Manage Hypervisor + NAS** | High | Medium | Proxmox + TrueNAS APIs. Resource monitoring, snapshot management, storage alerts. |

### Phase 3: Medium Value, Medium-High Complexity

| # | Agent | Criticality | Complexity | Notes |
|---|---|---|---|---|
| 9 | **Public Relations: Social Media** | Medium | High | X API costs $100/mo. Instagram requires Facebook Business. Immich integration for photo sourcing. All posts approval-gated. Start with LinkedIn (free API for posting). |
| 10 | **House Manager: Maintenance Scheduler** | Medium | Medium | Tenant request intake via messaging, contractor scheduling, work order tracking. Small DB schema for work orders. |
| 11 | **Tech Chair: Migrations + Architecture Docs** | Medium | Medium | Analyze current container/VM topology, suggest optimizations. Auto-generate architecture diagrams. |
| 12 | **Social Chair: Event + Travel Planning** | Medium | Medium | RAG over venue/restaurant data, calendar integration, budget-aware planning. |

### Phase 4: Lower Criticality or High Complexity

| # | Agent | Criticality | Complexity | Notes |
|---|---|---|---|---|
| 13 | **Treasurer: Financial Planning** | Medium | High | Long-term projections, investment suggestions. Requires robust financial data from Phase 2 to be useful. |
| 14 | **Professional Relations: Networker** | Medium | High | LinkedIn DM management is tricky — LinkedIn actively blocks automation. May need a browser-based approach (Playwright). |
| 15 | **House Doctor: Trainer + Dietician** | Low-Med | Medium | No wearable data yet. Start with manual input, meal planning, workout generation. Value increases dramatically with a wearable. |
| 16 | **Social Chair: Wedding Planner** | Medium | Medium | Useful but time-bounded. Vendor research, budget tracking, checklist management. |
| 17 | **Media Expert: Clip Retrieval + Any-in/Any-out** | Low-Med | High | Transcription, scene search, format conversion. Compute-heavy. Intel Arc has limited ML ecosystem vs NVIDIA. |
| 18 | **House Doctor: Physician/Therapist** | Low | Medium | Sensitive domain. Useful for journaling prompts, mood tracking, sleep hygiene suggestions. Keep expectations modest — not medical advice. |
| 19 | **Public Relations: Brand Management** | Low-Med | Medium | Content calendar, brand voice guidelines, competitive analysis. Builds on Phase 3 social media foundation. |
| 20 | **Social Chair: Party Idea Generator** | Low | Low | Fun but low stakes. Simple prompt engineering on top of the base framework. Build whenever. |

---

## 6. Tech Stack Summary

| Layer | Technology | Runs On |
|---|---|---|
| Interface | discord.py + python-telegram-bot | CPU node |
| Orchestration | LangGraph (Python) | CPU node |
| Agent Runtime | LangGraph agents w/ OpenRouter | CPU node |
| Tool Layer | MCP servers (Python/TypeScript) | CPU node |
| Vision Tasks | OpenRouter vision models (or local via Frigate) | GPU node (Frigate), cloud (analysis) |
| Database | PostgreSQL 16 | Existing VM or container |
| Cache/Queue | Redis | Container |
| Vector Store | Qdrant or ChromaDB | Container |
| Event Bus | Mosquitto MQTT (likely existing) | Existing |
| Secrets | Docker secrets or Vault | CPU node |

---

## 7. Key Risks & Callouts

- **LinkedIn automation**: LinkedIn aggressively blocks bots. The Networker agent will be the hardest to build reliably. Consider starting with email-based networking only.
- **X/Twitter API cost**: $100/month for basic posting access. Evaluate if the posting volume justifies it.
- **Intel Arc ML support**: Limited compared to NVIDIA CUDA. For any heavy inference, lean on OpenRouter cloud models rather than trying to run local models on Arc.
- **Plaid costs**: Free in development (100 accounts). Production is ~$0.30/connection/month + per-call fees. Still far cheaper than Monarch.
- **WhatsApp**: Requires Meta Business verification and has strict template message rules. Deprioritize until Discord + Telegram are solid.
- **Sensitive data**: Financial data, health data, tenant PII — all need encryption at rest in the DB. Don't store credentials in plaintext configs.
- **Fiancee's brand accounts**: Social media agents managing multiple brand identities (personal x2, design business, future building business) need clear persona isolation to avoid cross-posting.

---

## 8. Timeline Estimates

| Phase | Duration | Deliverables |
|---|---|---|
| **Phase 0: Foundation** | 1-2 weeks | Orchestration skeleton, Discord/Telegram bots, shared infra (Postgres, Redis, Vector DB), OpenRouter wrapper |
| **Phase 1: Quick Wins** | 2-3 weeks | Container management, rent checker, media Q&A, network management |
| **Phase 2: Core Value** | 4-6 weeks | Finances/Plaid, surveillance review, job search/resume, hypervisor/NAS management |
| **Phase 3: Expansion** | 4-6 weeks | Social media, maintenance scheduler, migrations/docs, event planning |
| **Phase 4: Full Ecosystem** | Ongoing | Financial planning, LinkedIn networking, health/fitness, wedding, advanced media, brand management |

**Total estimated time to Phase 2 completion (functional core): ~2-3 months**
