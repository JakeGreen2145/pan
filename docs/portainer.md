# Portainer Integration

Pan's **Tech Chair** agent manages Docker containers through the [Portainer API](https://docs.portainer.io/api/access). This lets you list, inspect, start, stop, and restart containers — and read their logs — all from Discord.

## Prerequisites

- A running Portainer instance (CE or Business Edition)
- At least one Docker endpoint configured in Portainer
- An API key with access to that endpoint

## Generating an API Key

1. Log into Portainer
2. Click your username (top right) → **My Account**
3. Scroll to **Access Tokens** → **Add access token**
4. Name it (e.g. "pan") and click **Create access token**
5. Copy the token — this is your `PAN_PORTAINER__API_KEY`

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAN_PORTAINER__BASE_URL` | No | `https://portainer.local:9443` | Portainer URL including port |
| `PAN_PORTAINER__API_KEY` | Yes | — | API access token |
| `PAN_PORTAINER__ENDPOINT_ID` | No | Auto-detected | Portainer endpoint ID. If omitted, Pan uses the first endpoint found. |
| `PAN_PORTAINER__VERIFY_SSL` | No | `false` | Set to `true` if Portainer has a valid TLS certificate |

### Endpoint auto-detection

If `PAN_PORTAINER__ENDPOINT_ID` is not set, Pan calls `GET /api/endpoints` on startup and caches the first endpoint's ID for all subsequent requests. Set it explicitly if you have multiple endpoints.

## Available Tools

These tools are exposed to the Tech Chair agent and called via the Portainer Docker proxy API (`/api/endpoints/{id}/docker/...`):

| Tool | Description | Args |
|------|-------------|------|
| `list_containers` | List all containers with name, state, status, image, and ID | `status_filter`: `running`, `stopped`, or `all` (default) |
| `get_container_details` | Inspect a single container (image, state, ports, mounts, restart count) | `container_id`: ID or name |
| `restart_container` | Restart a container | `container_id` |
| `stop_container` | Stop a running container | `container_id` |
| `start_container` | Start a stopped container | `container_id` |
| `get_container_logs` | Fetch recent stdout/stderr logs | `container_id`, `tail` (default: 100 lines) |

All tools return formatted strings (not raw JSON) so the LLM can include them directly in its response. Errors are caught and returned as descriptive messages rather than raised.

## Connection Details

Pan connects to Portainer using `httpx.AsyncClient` with:

- **Authentication**: `X-API-Key` header
- **Timeout**: 30 seconds per request
- **SSL verification**: Controlled by `PAN_PORTAINER__VERIFY_SSL`

## Troubleshooting

| Problem | Check |
|---------|-------|
| `Error connecting to Portainer` | Verify `BASE_URL` is reachable from where Pan runs. Check firewall/DNS. |
| `No Portainer endpoints found` | Log into Portainer and confirm at least one endpoint exists under **Environments**. |
| `401` or `403` errors | API key may be expired or lack permissions. Regenerate from **My Account → Access Tokens**. |
| `404` on container operations | Container name/ID may be wrong. Use `list_containers` first to get valid names. |
| SSL errors | Set `PAN_PORTAINER__VERIFY_SSL=false` for self-signed certs, or install the CA cert. |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/agents/tech_chair/tools.py` | Tool definitions, `_portainer_client()` context manager |
| `src/pan/agents/tech_chair/agent.py` | Agent creation, tool registration |
| `src/pan/config/settings.py` | `PortainerSettings` model |
| `src/pan/config/prompts/tech_chair.txt` | Tech Chair system prompt |
