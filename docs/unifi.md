# UniFi Integration

Pan's **Tech Chair** agent monitors network infrastructure through the official [UniFi Network Integration API](https://help.ui.com/hc/en-us/articles/30076656117655) on your gateway device. You can check network health, see connected clients, view device status, and list port forwarding rules from Discord.

## Prerequisites

- A Ubiquiti gateway running UniFi OS (Cloud Gateway Max, UDM Pro, UDM SE, etc.)
- UniFi Network 8.0 or later
- An API key generated from the UniFi OS console

## Creating an API Key

1. Open the UniFi OS console on your gateway (e.g., `https://192.168.1.1`)
2. Go to **Settings** → **Control Plane** → **Integrations**
3. Click **Create API Key**
4. Name it (e.g., "pan") and select **Network** as the scope
5. Copy the key — this is your `PAN_UNIFI__API_KEY`

## Configuration

```env
PAN_UNIFI__BASE_URL=https://192.168.1.1
PAN_UNIFI__API_KEY=your-unifi-api-key
PAN_UNIFI__VERIFY_SSL=false
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAN_UNIFI__BASE_URL` | No | `https://unifi.local` | Gateway IP or hostname (HTTPS required) |
| `PAN_UNIFI__API_KEY` | Yes | — | API key from Settings → Control Plane → Integrations |
| `PAN_UNIFI__VERIFY_SSL` | No | `false` | UDMs use self-signed certs by default |

### Authentication

Pan uses the official **Integration API** with `X-API-Key` header authentication. No login, cookies, or CSRF tokens required. The API key is scoped to the Network application and provides read access to sites, devices, clients, and port forwarding rules.

The site ID is auto-discovered on first request by querying `/v1/sites` and cached for subsequent calls.

## Available Tools

| Tool | Description | Key Args |
|------|-------------|----------|
| `get_network_health` | Subsystem health for WAN, WLAN, LAN, VPN — status, adopted devices, latency | — |
| `list_network_devices` | All APs, switches, gateway — name, model, IP, state, firmware, upgradable | — |
| `list_network_clients` | Connected clients with hostname, IP, signal strength, uptime | `wired_only`, `wireless_only` |
| `get_wan_info` | WAN IP, uplink speed, uptime, last speed test results | — |
| `list_port_forwards` | Port forwarding rules with ports, destination IP, protocol, enabled status | — |

The `list_network_clients` tool caps output at 50 clients to keep responses manageable. It reports the total count if there are more.

## Connection Details

- **Authentication**: `X-API-Key` header (stateless, no session management)
- **API base**: `{BASE_URL}/proxy/network/integration/v1`
- **Endpoints**: `/v1/sites`, `/v1/sites/{siteId}/devices`, `/v1/sites/{siteId}/clients`, etc.
- **Pagination**: Responses include `offset`, `limit`, `totalCount` — Pan auto-pages through all results
- **Timeout**: 30 seconds per request
- **SSL**: Self-signed by default — set `VERIFY_SSL=false`

## Troubleshooting

| Problem | Check |
|---------|-------|
| `Error connecting to UniFi` | Verify `BASE_URL` is the gateway's IP on HTTPS (not HTTP). |
| `401` errors | API key may be invalid or expired. Regenerate in Settings → Control Plane → Integrations. |
| `No UniFi sites found` | The API key may not have Network scope. Recreate with Network selected. |
| Empty device list | Ensure devices are adopted in the UniFi Network application. |
| `403` errors | API key is read-only by default. Write operations are not supported. |

## Supported Hardware

Pan has been tested with:
- Cloud Gateway Max (gateway + controller)
- USW Pro Max 16 PoE (managed switch)
- U7 Pro / U7 Pro Max (WiFi 7 APs)

Any UniFi OS device running the Network application should work.

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/agents/tech_chair/unifi_tools.py` | Tool definitions, `_unifi_client()` context manager |
| `src/pan/config/settings.py` | `UniFiSettings` |
