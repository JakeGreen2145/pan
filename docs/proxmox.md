# Proxmox VE Integration

Pan's **Tech Chair** agent manages virtual machines and LXC containers through the [Proxmox VE API](https://pve.proxmox.com/pve-docs/api-viewer/). You can list VMs, check resource usage, and start/stop/reboot machines from Discord.

## Prerequisites

- A running Proxmox VE node (tested with PVE 8.x)
- An API token with appropriate permissions

## Creating an API Token

SSH into your Proxmox host and run:

```bash
# Create a token named "pan" for root (no privilege separation for simplicity)
pveum user token add root@pam pan --privsep=0
```

This outputs a token value like:

```
┌──────────────┬──────────────────────────────────────┐
│ key          │ value                                │
├──────────────┼──────────────────────────────────────┤
│ full-tokenid │ root@pam!pan                         │
├──────────────┼──────────────────────────────────────┤
│ info         │ {"privsep":"0"}                      │
├──────────────┼──────────────────────────────────────┤
│ value        │ xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx │
└──────────────┴──────────────────────────────────────┘
```

Your `PAN_PROXMOX__API_TOKEN` is the full token string: `root@pam!pan=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

For a more restricted setup, create a dedicated user and role instead of using root.

## Configuration

```env
PAN_PROXMOX__BASE_URL=https://192.168.1.10:8006
PAN_PROXMOX__API_TOKEN=root@pam!pan=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PAN_PROXMOX__NODE_NAME=pve
PAN_PROXMOX__VERIFY_SSL=false
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAN_PROXMOX__BASE_URL` | No | `https://proxmox.local:8006` | Proxmox web UI URL |
| `PAN_PROXMOX__API_TOKEN` | Yes | — | Full API token string (`USER@REALM!TOKENID=UUID`) |
| `PAN_PROXMOX__NODE_NAME` | No | `pve` | Name of the Proxmox node (shown in the PVE UI sidebar) |
| `PAN_PROXMOX__VERIFY_SSL` | No | `false` | Set to `true` if you've installed a valid TLS certificate |

## Available Tools

| Tool | Description | Key Args |
|------|-------------|----------|
| `list_vms` | List all VMs and LXC containers with VMID, name, status, CPU, memory | — |
| `get_vm_status` | Detailed stats for a specific VM/container (CPU, memory, disk, network, uptime) | `vmid` |
| `start_vm` | Start a stopped VM or container | `vmid` |
| `stop_vm` | Graceful ACPI shutdown | `vmid` |
| `reboot_vm` | Reboot a running VM or container | `vmid` |
| `get_node_status` | Physical host stats (CPU, memory, disk, kernel version) | — |

VMs and containers are identified by their **VMID** (the number shown in the Proxmox UI). The tools automatically determine whether a VMID is a QEMU VM or LXC container and use the correct API path.

Power control operations (`start_vm`, `stop_vm`, `reboot_vm`) return a Proxmox task UPID. The operation runs asynchronously on the Proxmox side.

## Connection Details

- **Authentication**: `Authorization: PVEAPIToken=...` header (not Bearer)
- **Base path**: `/api2/json` appended to the configured URL
- **Timeout**: 30 seconds per request
- **SSL**: Self-signed by default — set `VERIFY_SSL=false`

## Troubleshooting

| Problem | Check |
|---------|-------|
| `Error connecting to Proxmox` | Verify `BASE_URL` is reachable on port 8006. Check firewall. |
| `401` errors | Token format must be `USER@REALM!TOKENID=UUID`. No `Bearer` prefix. |
| `VM not found` | Verify the VMID exists. Run `list_vms` first. |
| `Permission denied` on start/stop | Token may need `VM.PowerMgmt` privilege. Using `--privsep=0` avoids this. |
| Wrong node name | Check `PAN_PROXMOX__NODE_NAME` matches the name shown in the Proxmox sidebar. |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/agents/tech_chair/proxmox_tools.py` | Tool definitions, `_proxmox_client()`, `_get_resource_info()` |
| `src/pan/config/settings.py` | `ProxmoxSettings` |
