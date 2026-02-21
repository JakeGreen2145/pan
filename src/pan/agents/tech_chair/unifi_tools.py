from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings

logger = structlog.get_logger()

_cached_site_id: str | None = None


def _time_since(iso_timestamp: str | None) -> str:
    if not iso_timestamp:
        return "N/A"
    try:
        connected = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        delta = datetime.now(UTC) - connected
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        return " ".join(parts) or "0m"
    except (ValueError, TypeError):
        return "N/A"


@asynccontextmanager
async def _unifi_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    settings = get_settings().unifi
    headers = {
        "X-API-Key": settings.api_key.get_secret_value(),
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(
        base_url=f"{settings.base_url}/proxy/network/integration",
        headers=headers,
        verify=settings.verify_ssl,
        timeout=30.0,
    ) as client:
        yield client


async def _get_site_id(client: httpx.AsyncClient) -> str:
    global _cached_site_id
    if _cached_site_id is not None:
        return _cached_site_id

    resp = await client.get("/v1/sites")
    resp.raise_for_status()
    sites = resp.json().get("data", [])
    if not sites:
        raise ValueError("No UniFi sites found.")
    _cached_site_id = sites[0]["id"]
    logger.info("unifi_site_discovered", site_id=_cached_site_id)
    return _cached_site_id


async def _get_all_pages(client: httpx.AsyncClient, path: str, *, limit: int = 200) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        resp = await client.get(path, params={"offset": offset, "limit": limit})
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])
        items.extend(data)
        total = body.get("totalCount", len(items))
        offset += len(data)
        if offset >= total or not data:
            break
    return items


@tool
async def get_network_health() -> str:
    """Get UniFi network health — sites, device counts, and network list."""
    try:
        async with _unifi_client() as client:
            resp = await client.get("/v1/sites")
            resp.raise_for_status()
            sites = resp.json().get("data", [])

            if not sites:
                return "No UniFi sites found."

            site_id = sites[0]["id"]
            devices = await _get_all_pages(client, f"/v1/sites/{site_id}/devices")
            networks = await _get_all_pages(client, f"/v1/sites/{site_id}/networks")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"

    online = sum(1 for d in devices if d.get("state") == "ONLINE")
    offline = sum(1 for d in devices if d.get("state") != "ONLINE")

    lines = [
        f"UniFi Network Health — {sites[0].get('name', 'Default')}",
        "",
        f"  Devices: {online} online, {offline} offline ({len(devices)} total)",
        "",
        "  Devices:",
    ]
    for dev in devices:
        name = dev.get("name", "unknown")
        state = dev.get("state", "?")
        model = dev.get("model", "?")
        icon = "🟢" if state == "ONLINE" else "🔴"
        lines.append(f"    {icon} {name} ({model}) — {state}")

    if networks:
        lines.append("")
        lines.append("  Networks:")
        for net in networks:
            net_name = net.get("name", "?")
            vlan = net.get("vlanId", "?")
            enabled = "enabled" if net.get("enabled") else "disabled"
            lines.append(f"    {net_name} (VLAN {vlan}) — {enabled}")

    return "\n".join(lines)


@tool
async def list_network_devices() -> str:
    """List all UniFi network devices (APs, switches, gateways) with status and firmware."""
    try:
        async with _unifi_client() as client:
            site_id = await _get_site_id(client)
            devices = await _get_all_pages(client, f"/v1/sites/{site_id}/devices")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"
    except ValueError as e:
        return str(e)

    if not devices:
        return "No network devices found."

    header = f"{'NAME':<25} {'MODEL':<20} {'IP':<16} {'MAC':<18} {'STATE':<8} {'FW'}"
    lines = [header, "-" * len(header)]
    for dev in sorted(devices, key=lambda d: d.get("name", "")):
        name = dev.get("name", "unknown")
        model = dev.get("model", "?")
        ip = dev.get("ipAddress", "N/A")
        mac = dev.get("macAddress", "N/A")
        state = dev.get("state", "?")
        fw = dev.get("firmwareVersion", "?")
        lines.append(f"{name:<25} {model:<20} {ip:<16} {mac:<18} {state:<8} {fw}")

    return "\n".join(lines)


@tool
async def list_network_clients(wired_only: bool = False, wireless_only: bool = False) -> str:
    """List connected network clients with IP, MAC, and connection type.

    Args:
        wired_only: Show only wired clients.
        wireless_only: Show only wireless clients.
    """
    try:
        async with _unifi_client() as client:
            site_id = await _get_site_id(client)
            clients = await _get_all_pages(client, f"/v1/sites/{site_id}/clients")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"
    except ValueError as e:
        return str(e)

    if wired_only:
        clients = [c for c in clients if c.get("type") == "WIRED"]
    elif wireless_only:
        clients = [c for c in clients if c.get("type") == "WIRELESS"]

    total = len(clients)
    if not clients:
        return "No clients found."

    clients.sort(key=lambda c: (c.get("name") or c.get("macAddress", "")).lower())

    header = f"{'NAME':<30} {'IP':<16} {'MAC':<18} {'TYPE':<10} {'CONNECTED'}"
    lines = [header, "-" * len(header)]
    for cl in clients[:50]:
        name = cl.get("name") or cl.get("macAddress", "unknown")
        ip = cl.get("ipAddress", "N/A")
        mac = cl.get("macAddress", "N/A")
        conn_type = cl.get("type", "?")
        connected = _time_since(cl.get("connectedAt"))
        lines.append(f"{name:<30} {ip:<16} {mac:<18} {conn_type:<10} {connected}")

    if total > 50:
        lines.append(f"\n(Showing 50 of {total} clients)")

    return "\n".join(lines)


@tool
async def get_wan_info() -> str:
    """Get WAN/gateway device details including IP, firmware, and port status."""
    try:
        async with _unifi_client() as client:
            site_id = await _get_site_id(client)
            devices = await _get_all_pages(client, f"/v1/sites/{site_id}/devices")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"
    except ValueError as e:
        return str(e)

    gateway = None
    for dev in devices:
        model = (dev.get("model") or "").lower()
        name = (dev.get("name") or "").lower()
        if any(kw in model or kw in name for kw in ("gw", "udm", "ucg", "gateway")):
            gateway = dev
            break

    if not gateway:
        return "No gateway device found."

    gw_id = gateway.get("id")
    if gw_id:
        try:
            async with _unifi_client() as client:
                site_id = await _get_site_id(client)
                resp = await client.get(f"/v1/sites/{site_id}/devices/{gw_id}")
                resp.raise_for_status()
                gateway = resp.json()
        except httpx.HTTPError:
            pass

    lines = [
        "WAN / Gateway Info:",
        f"  Name:     {gateway.get('name', 'Gateway')}",
        f"  Model:    {gateway.get('model', '?')}",
        f"  IP:       {gateway.get('ipAddress', 'N/A')}",
        f"  MAC:      {gateway.get('macAddress', 'N/A')}",
        f"  State:    {gateway.get('state', '?')}",
        f"  Firmware: {gateway.get('firmwareVersion', '?')}",
    ]

    interfaces = gateway.get("interfaces", {})
    if isinstance(interfaces, dict):
        ports = interfaces.get("ports", [])
        if ports:
            lines.append("")
            lines.append("  Ports:")
            for port in ports:
                idx = port.get("idx", "?")
                state = port.get("state", "?")
                speed = port.get("speedMbps", "?")
                max_speed = port.get("maxSpeedMbps", "?")
                lines.append(f"    Port {idx}: {state} ({speed}/{max_speed} Mbps)")

    return "\n".join(lines)


@tool
async def list_networks() -> str:
    """List all configured UniFi networks with VLAN and status info."""
    try:
        async with _unifi_client() as client:
            site_id = await _get_site_id(client)
            networks = await _get_all_pages(client, f"/v1/sites/{site_id}/networks")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"
    except ValueError as e:
        return str(e)

    if not networks:
        return "No networks configured."

    header = f"{'NAME':<25} {'VLAN':<8} {'TYPE':<15} {'ENABLED'}"
    lines = [header, "-" * len(header)]
    for net in networks:
        name = net.get("name", "?")
        vlan = str(net.get("vlanId", "?"))
        mgmt = net.get("management", "?")
        enabled = "yes" if net.get("enabled") else "no"
        lines.append(f"{name:<25} {vlan:<8} {mgmt:<15} {enabled}")

    return "\n".join(lines)
