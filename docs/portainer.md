# Portainer Integration

Pan's **Tech Chair** agent manages Docker containers through the [Portainer API](https://docs.portainer.io/api/access). Pan supports **multiple Portainer instances** — for example, a main server and a GPU host — each with its own URL and API key.

## Prerequisites

- One or more running Portainer instances (CE or Business Edition)
- At least one Docker endpoint configured per instance
- An API key per instance

## Generating an API Key

1. Log into Portainer
2. Click your username (top right) → **My Account**
3. Scroll to **Access Tokens** → **Add access token**
4. Name it (e.g. "pan") and click **Create access token**
5. Copy the token — repeat for each Portainer instance

## Configuration

Portainer uses a **multi-instance** configuration. Each instance is a named entry under `PAN_PORTAINER__INSTANCES`:

```env
# Main server
PAN_PORTAINER__INSTANCES__MAIN__BASE_URL=https://portainer.local:9443
PAN_PORTAINER__INSTANCES__MAIN__API_KEY=ptr_xxxx
PAN_PORTAINER__INSTANCES__MAIN__ENDPOINT_ID=1
PAN_PORTAINER__INSTANCES__MAIN__VERIFY_SSL=false

# GPU host
PAN_PORTAINER__INSTANCES__GPU__BASE_URL=https://gpu-host.local:9443
PAN_PORTAINER__INSTANCES__GPU__API_KEY=ptr_yyyy
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `BASE_URL` | Yes | — | Portainer URL including port |
| `API_KEY` | Yes | — | API access token |
| `ENDPOINT_ID` | No | Auto-detected | Docker endpoint ID. If omitted, Pan uses the first endpoint found. |
| `VERIFY_SSL` | No | `false` | Set to `true` if Portainer has a valid TLS certificate |

The instance name (`MAIN`, `GPU`, etc.) is the `instance` parameter in tool calls. Add as many as you need.

### Endpoint auto-detection

If `ENDPOINT_ID` is not set for an instance, Pan calls `GET /api/endpoints` on the first request and caches the first endpoint's ID for all subsequent requests to that instance.

## Available Tools

| Tool | Description | Key Args |
|------|-------------|----------|
| `list_portainer_instances` | List all configured Portainer instances | — |
| `list_containers` | List all containers with name, state, image, ID | `instance`, `status_filter` |
| `get_container_details` | Inspect a container (image, state, ports, mounts) | `container_id`, `instance` |
| `restart_container` | Restart a container | `container_id`, `instance` |
| `stop_container` | Stop a running container | `container_id`, `instance` |
| `start_container` | Start a stopped container | `container_id`, `instance` |
| `get_container_logs` | Fetch recent stdout/stderr logs | `container_id`, `tail`, `instance` |

All tools default to `instance="main"`. The agent will ask which instance to target if the user doesn't specify.

## Connection Details

- **Authentication**: `X-API-Key` header per instance
- **Timeout**: 30 seconds per request
- **SSL verification**: Controlled per instance via `VERIFY_SSL`

## Troubleshooting

| Problem | Check |
|---------|-------|
| `Unknown Portainer instance` | Verify instance name in `.env`. Run `list_portainer_instances` to see configured names. |
| `Error connecting to Portainer` | Verify `BASE_URL` is reachable. Check firewall/DNS. |
| `No endpoints found` | Log into Portainer and confirm at least one endpoint exists under **Environments**. |
| `401` or `403` errors | API key may be expired. Regenerate from **My Account → Access Tokens**. |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/agents/tech_chair/portainer_tools.py` | Tool definitions, `_portainer_client()` context manager |
| `src/pan/agents/tech_chair/agent.py` | Agent creation, tool registration |
| `src/pan/config/settings.py` | `PortainerSettings`, `PortainerInstanceSettings` |
