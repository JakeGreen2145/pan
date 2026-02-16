"""TrueNAS Scale REST API tools for storage and system monitoring."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def _truenas_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    settings = get_settings().truenas
    headers = {"Authorization": f"Bearer {settings.api_key.get_secret_value()}"}

    async with httpx.AsyncClient(
        base_url=settings.base_url,
        headers=headers,
        verify=settings.verify_ssl,
        timeout=30.0,
    ) as client:
        yield client


def _format_bytes(n: int | float | None) -> str:
    if n is None:
        return "N/A"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


@tool
async def get_storage_summary() -> str:
    """Get a summary of all ZFS storage pools with status and space usage.

    Shows each pool's name, health status, and total/used/free space.
    """
    try:
        async with _truenas_client() as client:
            resp = await client.get("/pool")
            resp.raise_for_status()
            pools = resp.json()
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    if not pools:
        return "No storage pools found."

    header = f"{'POOL':<20} {'STATUS':<12} {'TOTAL':<12} {'USED':<12} {'FREE':<12}"
    lines = [header, "-" * len(header)]

    for pool in sorted(pools, key=lambda p: p.get("name", "")):
        name = pool.get("name", "unknown")
        status = pool.get("status", "UNKNOWN")
        topology = pool.get("topology", {})
        total = pool.get("size", None)
        allocated = pool.get("allocated", None)
        free = pool.get("free", None)

        if total is None and topology:
            total = pool.get("size")
        if allocated is None:
            allocated = pool.get("allocated")
        if free is None:
            free = pool.get("free")

        lines.append(
            f"{name:<20} {status:<12} "
            f"{_format_bytes(total):<12} "
            f"{_format_bytes(allocated):<12} "
            f"{_format_bytes(free):<12}"
        )

    return "\n".join(lines)


@tool
async def list_datasets(pool_name: str | None = None) -> str:
    """List ZFS datasets with usage and compression info.

    Args:
        pool_name: Filter datasets by pool name. Shows all if not specified.
    """
    try:
        async with _truenas_client() as client:
            resp = await client.get("/pool/dataset")
            resp.raise_for_status()
            datasets = resp.json()
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    if pool_name:
        datasets = [
            d for d in datasets if d.get("pool", d.get("name", "").split("/")[0]) == pool_name
        ]

    if not datasets:
        return f"No datasets found{f' for pool {pool_name!r}' if pool_name else ''}."

    lines = [f"{'DATASET':<40} {'USED':<12} {'AVAIL':<12} {'COMPRESS':<10} {'MOUNTPOINT'}"]
    lines.append("-" * len(lines[0]))

    for ds in sorted(datasets, key=lambda d: d.get("name", "")):
        name = ds.get("name", "unknown")
        used = ds.get("used", {}).get("parsed") or ds.get("used", {}).get("rawvalue")
        avail = ds.get("available", {}).get("parsed") or ds.get("available", {}).get("rawvalue")
        compression = ds.get("compression", {}).get("value", "off")
        mountpoint = ds.get("mountpoint", {}).get("value", "-")

        used_str = _format_bytes(int(used)) if used else "N/A"
        avail_str = _format_bytes(int(avail)) if avail else "N/A"

        lines.append(f"{name:<40} {used_str:<12} {avail_str:<12} {compression:<10} {mountpoint}")

    return "\n".join(lines)


@tool
async def list_snapshots(dataset: str | None = None) -> str:
    """List recent ZFS snapshots, optionally filtered by dataset.

    Args:
        dataset: Filter snapshots to this dataset name. Shows all if not specified.
    """
    try:
        async with _truenas_client() as client:
            params: dict[str, str] = {}
            if dataset:
                params["dataset"] = dataset
            resp = await client.get("/zfs/snapshot", params=params)
            resp.raise_for_status()
            snapshots = resp.json()
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    if not snapshots:
        return f"No snapshots found{f' for dataset {dataset!r}' if dataset else ''}."

    snapshots.sort(
        key=lambda s: s.get("properties", {}).get("creation", {}).get("parsed", ""),
        reverse=True,
    )
    snapshots = snapshots[:20]

    lines = [f"{'SNAPSHOT':<50} {'DATASET':<30} {'CREATED':<22} {'REFERENCED'}"]
    lines.append("-" * len(lines[0]))

    for snap in snapshots:
        name = snap.get("snapshot_name", snap.get("name", "unknown"))
        ds = snap.get("dataset", "unknown")
        props = snap.get("properties", {})
        created_raw = props.get("creation", {}).get("parsed")
        referenced = props.get("referenced", {}).get("rawvalue")

        if created_raw:
            try:
                created = datetime.fromtimestamp(int(created_raw), tz=UTC).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                created = str(created_raw)
        else:
            created = "N/A"

        ref_str = _format_bytes(int(referenced)) if referenced else "N/A"
        lines.append(f"{name:<50} {ds:<30} {created:<22} {ref_str}")

    return "\n".join(lines)


@tool
async def get_disk_health() -> str:
    """Get disk health status including SMART data for all installed disks.

    Shows disk name, model, serial number, temperature, and SMART status.
    """
    try:
        async with _truenas_client() as client:
            resp = await client.get("/disk")
            resp.raise_for_status()
            disks = resp.json()

            smart_results: dict[str, dict] = {}
            try:
                smart_resp = await client.get("/smart/test/results")
                smart_resp.raise_for_status()
                for result in smart_resp.json():
                    disk_name = result.get("disk")
                    if disk_name:
                        smart_results[disk_name] = result
            except httpx.HTTPError:
                logger.debug("smart_results_unavailable")
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    if not disks:
        return "No disks found."

    header = f"{'DISK':<10} {'MODEL':<30} {'SERIAL':<20} {'SIZE':<12} {'TEMP':<8} {'SMART'}"
    lines = [header, "-" * len(header)]

    for disk in sorted(disks, key=lambda d: d.get("name", "")):
        name = disk.get("name", "unknown")
        model = disk.get("model", "unknown")[:28]
        serial = disk.get("serial", "unknown")[:18]
        size = disk.get("size")
        size_str = _format_bytes(size) if size else "N/A"

        temp = disk.get("temperature")
        temp_str = f"{temp}°C" if temp is not None else "N/A"

        smart = smart_results.get(name, {})
        smart_status = smart.get("status", "N/A") if smart else "N/A"

        lines.append(
            f"{name:<10} {model:<30} {serial:<20} {size_str:<12} {temp_str:<8} {smart_status}"
        )

    return "\n".join(lines)


@tool
async def get_truenas_alerts() -> str:
    """Get active (non-dismissed) TrueNAS alerts.

    Shows alert level, message, timestamp, and dismissed status.
    """
    try:
        async with _truenas_client() as client:
            resp = await client.get("/alert/list")
            resp.raise_for_status()
            alerts = resp.json()
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    active_alerts = [a for a in alerts if not a.get("dismissed", False)]

    if not active_alerts:
        return "No active alerts. All clear."

    lines = [f"Active alerts ({len(active_alerts)}):", ""]
    for alert in active_alerts:
        level = alert.get("level", "UNKNOWN")
        msg = alert.get("formatted", alert.get("message", "No message"))
        dt = alert.get("datetime", {}).get("$date")
        if dt:
            try:
                ts = datetime.fromtimestamp(dt / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                ts = str(dt)
        else:
            ts = "N/A"

        lines.append(f"  [{level}] {msg}")
        lines.append(f"          {ts}")
        lines.append("")

    return "\n".join(lines).rstrip()


@tool
async def get_system_info() -> str:
    """Get TrueNAS system information including version, hostname, and uptime.

    Retrieves system details and general configuration.
    """
    try:
        async with _truenas_client() as client:
            info_resp = await client.get("/system/info")
            info_resp.raise_for_status()
            info = info_resp.json()

            general: dict = {}
            try:
                gen_resp = await client.get("/system/general")
                gen_resp.raise_for_status()
                general = gen_resp.json()
            except httpx.HTTPError:
                logger.debug("system_general_unavailable")
    except httpx.HTTPStatusError as e:
        return f"TrueNAS error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to TrueNAS: {e}"

    version = info.get("version", "unknown")
    hostname = info.get("hostname", "unknown")
    uptime_secs = info.get("uptime_seconds", info.get("uptime"))
    model = info.get("system_product", info.get("model", "unknown"))

    if uptime_secs and isinstance(uptime_secs, int | float):
        days = int(uptime_secs) // 86400
        hours = (int(uptime_secs) % 86400) // 3600
        uptime_str = f"{days}d {hours}h"
    else:
        uptime_str = str(uptime_secs) if uptime_secs else "N/A"

    timezone = general.get("timezone", "N/A")
    language = general.get("language", "N/A")

    lines = [
        "TrueNAS System Info",
        "-" * 40,
        f"  Version:    {version}",
        f"  Hostname:   {hostname}",
        f"  Model:      {model}",
        f"  Uptime:     {uptime_str}",
        f"  Timezone:   {timezone}",
        f"  Language:   {language}",
    ]

    return "\n".join(lines)
