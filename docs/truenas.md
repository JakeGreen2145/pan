# TrueNAS Scale Integration

Pan's **Tech Chair** agent monitors ZFS storage through the [TrueNAS Scale REST API](https://www.truenas.com/docs/api/). You can check pool health, dataset usage, snapshots, disk SMART status, and system alerts from Discord.

## Prerequisites

- TrueNAS Scale (Linux-based, not CORE/FreeBSD)
- An API key

## Creating an API Key

1. Log into the TrueNAS web UI
2. Click the user icon (top right) → **API Keys**
3. Click **Add** → name it (e.g. "pan") → **Add**
4. Copy the key — this is your `PAN_TRUENAS__API_KEY`

The API key has the same permissions as the user that created it.

## Configuration

```env
PAN_TRUENAS__BASE_URL=https://truenas.local/api/v2.0
PAN_TRUENAS__API_KEY=1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAN_TRUENAS__VERIFY_SSL=false
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAN_TRUENAS__BASE_URL` | No | `https://truenas.local/api/v2.0` | TrueNAS API URL (must include `/api/v2.0`) |
| `PAN_TRUENAS__API_KEY` | Yes | — | API key from the TrueNAS UI |
| `PAN_TRUENAS__VERIFY_SSL` | No | `false` | Set to `true` if you've installed a valid TLS certificate |

## Available Tools

| Tool | Description | Key Args |
|------|-------------|----------|
| `get_storage_summary` | Overview of all ZFS pools — name, health status, total/used/free space | — |
| `list_datasets` | List datasets with used/available space, compression, mountpoint | `pool_name` (optional filter) |
| `list_snapshots` | Recent snapshots with creation time and referenced size (max 20) | `dataset` (optional filter) |
| `get_disk_health` | All disks with model, serial, size, temperature, SMART status | — |
| `get_truenas_alerts` | Active (non-dismissed) system alerts with level and timestamp | — |
| `get_system_info` | TrueNAS version, hostname, model, uptime, timezone | — |

## Connection Details

- **Authentication**: `Authorization: Bearer <api_key>` header
- **Timeout**: 30 seconds per request
- **SSL**: Self-signed by default — set `VERIFY_SSL=false`

## Troubleshooting

| Problem | Check |
|---------|-------|
| `Error connecting to TrueNAS` | Verify `BASE_URL` is reachable. Make sure it includes `/api/v2.0`. |
| `401` errors | API key may be expired or invalid. Regenerate in the TrueNAS UI. |
| No pools shown | Verify pools exist in Storage → Pools in the TrueNAS UI. |
| SMART data unavailable | SMART monitoring may need to be enabled per disk in the TrueNAS UI. The tool handles this gracefully and shows "N/A". |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/agents/tech_chair/truenas_tools.py` | Tool definitions, `_truenas_client()` |
| `src/pan/config/settings.py` | `TrueNASSettings` |
