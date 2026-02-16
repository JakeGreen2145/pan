from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings

logger = structlog.get_logger()

_cached_site_id: str | None = None


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
    """Get overall UniFi network health — lists all sites with device counts and status."""
    try:
        async with _unifi_client() as client:
            resp = await client.get("/v1/sites")
            resp.raise_for_status()
            sites = resp.json().get("data", [])
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"

    if not sites:
        return "No UniFi sites found."

    lines = ["UniFi Sites:", ""]
    for site in sites:
        name = site.get("name", "unknown")
        site_id = site.get("id", "?")
        desc = site.get("description", "")
        lines.append(f"  {name} (ID: {site_id})")
        if desc:
            lines.append(f"    Description: {desc}")

        statistics = site.get("statistics", {})
        if statistics:
            counts = statistics.get("counts", {})
            offline = counts.get("offlineDevice", 0)
            active = counts.get("activeDevice", 0)
            lines.append(f"    Active devices: {active}")
            if offline:
                lines.append(f"    Offline devices: {offline}")

        isp = site.get("internetStatus", {})
        if isp:
            isp_status = isp.get("status", "unknown")
            lines.append(f"    Internet: {isp_status}")

        lines.append("")

    return "\n".join(lines).rstrip()


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

    header = f"{'NAME':<25} {'MODEL':<20} {'IP':<16} {'MAC':<18} {'STATE':<12} {'FW'}"
    lines = [header, "-" * len(header)]
    for dev in sorted(devices, key=lambda d: d.get("name", d.get("mac", ""))):
        name = dev.get("name", dev.get("mac", "unknown"))
        model = dev.get("model", "?")
        ip = dev.get("ip", "N/A")
        mac = dev.get("mac", "N/A")
        state = dev.get("state", "unknown")
        fw = dev.get("firmwareVersion", dev.get("version", "?"))
        lines.append(f"{name:<25} {model:<20} {ip:<16} {mac:<18} {state:<12} {fw}")

    return "\n".join(lines)


@tool
async def list_network_clients(wired_only: bool = False, wireless_only: bool = False) -> str:
    """List connected network clients with IP, MAC, and connection info.

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
        clients = [c for c in clients if not c.get("is_wired") and c.get("type") != "WIRED"]

    total = len(clients)
    if not clients:
        return "No clients found."

    clients.sort(key=lambda c: (c.get("name") or c.get("hostname") or c.get("mac", "")).lower())

    header = f"{'NAME':<30} {'IP':<16} {'MAC':<18} {'TYPE':<10} {'UPTIME'}"
    lines = [header, "-" * len(header)]
    for cl in clients[:50]:
        name = cl.get("name") or cl.get("hostname") or cl.get("mac", "unknown")
        ip = cl.get("ip", "N/A")
        mac = cl.get("mac", "N/A")
        conn_type = cl.get("type", "?")
        uptime = _seconds_to_human(cl.get("uptime", 0))
        lines.append(f"{name:<30} {ip:<16} {mac:<18} {conn_type:<10} {uptime}")

    if total > 50:
        lines.append(f"\n(Showing 50 of {total} clients)")

    return "\n".join(lines)


@tool
async def get_wan_info() -> str:
    """Get WAN connection details including gateway device info."""
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
        features = dev.get("features", [])
        if isinstance(features, dict):
            is_gw = features.get("hasGateway")
        elif isinstance(features, list):
            is_gw = "hasGateway" in features
        else:
            is_gw = False
        if is_gw:
            gateway = dev
            break
    if gateway is None:
        for dev in devices:
            model = (dev.get("model") or "").lower()
            name = (dev.get("name") or "").lower()
            if any(kw in model or kw in name for kw in ("gw", "udm", "ucg", "gateway")):
                gateway = dev
                break

    if not gateway:
        return "No gateway device found in the device list."

    name = gateway.get("name", "Gateway")
    ip = gateway.get("ip", "N/A")
    mac = gateway.get("mac", "N/A")
    fw = gateway.get("firmwareVersion", gateway.get("version", "?"))
    state = gateway.get("state", "unknown")
    uptime = _seconds_to_human(gateway.get("uptime", 0))

    lines = [
        "WAN / Gateway Info:",
        f"  Name:     {name}",
        f"  IP:       {ip}",
        f"  MAC:      {mac}",
        f"  State:    {state}",
        f"  Firmware: {fw}",
        f"  Uptime:   {uptime}",
    ]

    interfaces = gateway.get("interfaces", [])
    for iface in interfaces:
        if isinstance(iface, dict):
            if iface.get("type") == "WAN":
                iface_name = iface.get("name", "WAN")
                iface_ip = iface.get("ip", "N/A")
                lines.append("")
                lines.append(f"  {iface_name}:")
                lines.append(f"    IP: {iface_ip}")
        elif isinstance(iface, str) and "wan" in iface.lower():
            lines.append(f"  Interface: {iface}")

    return "\n".join(lines)


@tool
async def list_port_forwards() -> str:
    """List all configured port forwarding rules on the UniFi gateway."""
    try:
        async with _unifi_client() as client:
            site_id = await _get_site_id(client)
            rules = await _get_all_pages(client, f"/v1/sites/{site_id}/port-forwarding")
    except httpx.HTTPError as e:
        return f"Error connecting to UniFi: {e}"
    except ValueError as e:
        return str(e)

    if not rules:
        return "No port forwarding rules configured."

    header = (
        f"{'NAME':<25} {'DST_PORT':<12} {'FWD_IP':<16} {'FWD_PORT':<12} {'PROTO':<8} {'ENABLED'}"
    )
    lines = [header, "-" * len(header)]
    for rule in rules:
        name = rule.get("name", "unnamed")
        dst_port = rule.get("destinationPort", rule.get("dst_port", "?"))
        fwd_ip = rule.get("forwardIp", rule.get("fwd", "?"))
        fwd_port = rule.get("forwardPort", rule.get("fwd_port", "?"))
        proto = rule.get("protocol", rule.get("proto", "both"))
        enabled = "yes" if rule.get("enabled", True) else "no"
        lines.append(f"{name:<25} {dst_port:<12} {fwd_ip:<16} {fwd_port:<12} {proto:<8} {enabled}")

    return "\n".join(lines)
