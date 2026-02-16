from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings

logger = structlog.get_logger()


def _bytes_to_human(n: int | float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PiB"


def _seconds_to_human(s: int | float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, _ = divmod(s, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) or "0m"


@asynccontextmanager
async def _proxmox_client() -> AsyncGenerator[tuple[httpx.AsyncClient, str], None]:
    settings = get_settings().proxmox
    async with httpx.AsyncClient(
        base_url=f"{settings.base_url}/api2/json",
        headers={"Authorization": f"PVEAPIToken={settings.api_token.get_secret_value()}"},
        verify=settings.verify_ssl,
        timeout=30.0,
    ) as client:
        yield client, settings.node_name


async def _get_resource_info(client: httpx.AsyncClient, vmid: int) -> tuple[str, str] | None:
    resp = await client.get("/cluster/resources", params={"type": "vm"})
    resp.raise_for_status()
    for resource in resp.json().get("data", []):
        if resource.get("vmid") == vmid:
            return resource["node"], resource["type"]
    return None


@tool
async def list_vms() -> str:
    """List all virtual machines and containers across the Proxmox cluster.

    Shows VMID, name, type (qemu/lxc), status, node, CPU usage, and memory usage
    in a formatted table sorted by VMID.
    """
    try:
        async with _proxmox_client() as (client, _node):
            resp = await client.get("/cluster/resources", params={"type": "vm"})
            resp.raise_for_status()
            vms = resp.json().get("data", [])
    except httpx.HTTPError as e:
        return f"Error connecting to Proxmox: {e}"

    if not vms:
        return "No VMs or containers found."

    vms.sort(key=lambda v: v.get("vmid", 0))

    header = (
        f"{'VMID':<8} {'NAME':<25} {'TYPE':<6} {'STATUS':<10} {'NODE':<12} {'CPU%':<8} {'MEMORY'}"
    )
    lines = [header, "-" * len(header)]
    for vm in vms:
        vmid = vm.get("vmid", "?")
        name = vm.get("name", "unknown")
        vm_type = vm.get("type", "?")
        status = vm.get("status", "unknown")
        node = vm.get("node", "?")
        cpu = vm.get("cpu", 0) * 100
        maxmem = vm.get("maxmem", 0)
        mem = vm.get("mem", 0)
        mem_str = f"{_bytes_to_human(mem)} / {_bytes_to_human(maxmem)}" if maxmem else "N/A"
        lines.append(
            f"{vmid:<8} {name:<25} {vm_type:<6} {status:<10} {node:<12} {cpu:<7.1f}% {mem_str}"
        )

    return "\n".join(lines)


@tool
async def get_vm_status(vmid: int) -> str:
    """Get detailed status of a specific VM or container.

    Args:
        vmid: The numeric VMID of the virtual machine or container.
    """
    try:
        async with _proxmox_client() as (client, _node):
            info = await _get_resource_info(client, vmid)
            if not info:
                return f"VM/container {vmid} not found."
            node, vm_type = info

            resp = await client.get(f"/nodes/{node}/{vm_type}/{vmid}/status/current")
            resp.raise_for_status()
            data = resp.json().get("data", {})
    except httpx.HTTPError as e:
        return f"Error connecting to Proxmox: {e}"

    name = data.get("name", "unknown")
    status = data.get("status", "unknown")
    uptime = _seconds_to_human(data.get("uptime", 0))
    cpus = data.get("cpus", "?")
    cpu_pct = data.get("cpu", 0) * 100
    maxmem = data.get("maxmem", 0)
    mem = data.get("mem", 0)
    maxdisk = data.get("maxdisk", 0)
    disk = data.get("disk", 0)
    netin = data.get("netin", 0)
    netout = data.get("netout", 0)

    return (
        f"VM {vmid} — {name}\n"
        f"  Status:  {status}\n"
        f"  Uptime:  {uptime}\n"
        f"  CPU:     {cpus} cores, {cpu_pct:.1f}% usage\n"
        f"  Memory:  {_bytes_to_human(mem)} / {_bytes_to_human(maxmem)}\n"
        f"  Disk:    {_bytes_to_human(disk)} / {_bytes_to_human(maxdisk)}\n"
        f"  Network: ↓ {_bytes_to_human(netin)} / ↑ {_bytes_to_human(netout)}"
    )


@tool
async def start_vm(vmid: int) -> str:
    """Start a stopped VM or container.

    Args:
        vmid: The numeric VMID of the virtual machine or container to start.
    """
    try:
        async with _proxmox_client() as (client, _node):
            info = await _get_resource_info(client, vmid)
            if not info:
                return f"VM/container {vmid} not found."
            node, vm_type = info

            resp = await client.post(f"/nodes/{node}/{vm_type}/{vmid}/status/start")
            resp.raise_for_status()
            upid = resp.json().get("data", "")
    except httpx.HTTPError as e:
        return f"Error starting VM {vmid}: {e}"

    logger.info("vm_started", vmid=vmid, node=node, upid=upid)
    return f"Start command sent for VM {vmid}. Task UPID: {upid}"


@tool
async def stop_vm(vmid: int) -> str:
    """Gracefully shut down a running VM or container via ACPI.

    Args:
        vmid: The numeric VMID of the virtual machine or container to stop.
    """
    try:
        async with _proxmox_client() as (client, _node):
            info = await _get_resource_info(client, vmid)
            if not info:
                return f"VM/container {vmid} not found."
            node, vm_type = info

            resp = await client.post(f"/nodes/{node}/{vm_type}/{vmid}/status/shutdown")
            resp.raise_for_status()
            upid = resp.json().get("data", "")
    except httpx.HTTPError as e:
        return f"Error stopping VM {vmid}: {e}"

    logger.info("vm_stopped", vmid=vmid, node=node, upid=upid)
    return f"Shutdown command sent for VM {vmid}. Task UPID: {upid}"


@tool
async def reboot_vm(vmid: int) -> str:
    """Reboot a running VM or container.

    Args:
        vmid: The numeric VMID of the virtual machine or container to reboot.
    """
    try:
        async with _proxmox_client() as (client, _node):
            info = await _get_resource_info(client, vmid)
            if not info:
                return f"VM/container {vmid} not found."
            node, vm_type = info

            resp = await client.post(f"/nodes/{node}/{vm_type}/{vmid}/status/reboot")
            resp.raise_for_status()
            upid = resp.json().get("data", "")
    except httpx.HTTPError as e:
        return f"Error rebooting VM {vmid}: {e}"

    logger.info("vm_rebooted", vmid=vmid, node=node, upid=upid)
    return f"Reboot command sent for VM {vmid}. Task UPID: {upid}"


@tool
async def get_node_status() -> str:
    """Get status of the Proxmox host node including CPU, memory, disk, and version info."""
    try:
        async with _proxmox_client() as (client, node):
            resp = await client.get(f"/nodes/{node}/status")
            resp.raise_for_status()
            data = resp.json().get("data", {})
    except httpx.HTTPError as e:
        return f"Error connecting to Proxmox: {e}"

    cpu_info = data.get("cpuinfo", {})
    mem = data.get("memory", {})
    rootfs = data.get("rootfs", {})
    kver = data.get("kversion", "unknown")
    pve_ver = data.get("pveversion", "unknown")
    uptime = _seconds_to_human(data.get("uptime", 0))
    cpu_pct = data.get("cpu", 0) * 100

    mem_total = mem.get("total", 0)
    mem_used = mem.get("used", 0)
    mem_free = mem.get("free", 0)
    disk_total = rootfs.get("total", 0)
    disk_used = rootfs.get("used", 0)
    disk_free = rootfs.get("avail", 0)

    return (
        f"Node: {node}\n"
        f"  Uptime:  {uptime}\n"
        f"  CPU:     {cpu_info.get('model', 'unknown')} — {cpu_info.get('cpus', '?')} cores,"
        f" {cpu_pct:.1f}% usage\n"
        f"  Memory:  {_bytes_to_human(mem_used)} / {_bytes_to_human(mem_total)}"
        f" ({_bytes_to_human(mem_free)} free)\n"
        f"  Disk:    {_bytes_to_human(disk_used)} / {_bytes_to_human(disk_total)}"
        f" ({_bytes_to_human(disk_free)} free)\n"
        f"  Kernel:  {kver}\n"
        f"  PVE:     {pve_ver}"
    )
