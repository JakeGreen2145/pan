"""Portainer API tools with multi-instance support.

Each tool accepts an `instance` parameter to target a specific Portainer
instance (defaults to "main"). Instances are configured via settings:
PAN_PORTAINER__INSTANCES__<NAME>__BASE_URL, etc.
"""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings

logger = structlog.get_logger()

_cached_endpoint_ids: dict[str, int] = {}


@asynccontextmanager
async def _portainer_client(
    instance: str,
) -> AsyncGenerator[tuple[httpx.AsyncClient, int] | str, None]:
    """Create an httpx client for the given Portainer instance.

    Yields (client, endpoint_id) on success, or a string error message
    if the instance is not found.
    """
    settings = get_settings().portainer
    if instance not in settings.instances:
        available = ", ".join(sorted(settings.instances.keys())) or "(none configured)"
        yield f"Unknown Portainer instance '{instance}'. Available: {available}"
        return

    inst = settings.instances[instance]
    headers = {"X-API-Key": inst.api_key.get_secret_value()}

    async with httpx.AsyncClient(
        base_url=inst.base_url,
        headers=headers,
        verify=inst.verify_ssl,
        timeout=30.0,
    ) as client:
        if inst.endpoint_id is not None:
            endpoint_id = inst.endpoint_id
        elif instance in _cached_endpoint_ids:
            endpoint_id = _cached_endpoint_ids[instance]
        else:
            resp = await client.get("/api/endpoints")
            resp.raise_for_status()
            endpoints = resp.json()
            if not endpoints:
                yield f"No endpoints found on Portainer instance '{instance}'."
                return
            endpoint_id = endpoints[0]["Id"]
            _cached_endpoint_ids[instance] = endpoint_id
            logger.info(
                "portainer_endpoint_discovered",
                instance=instance,
                endpoint_id=endpoint_id,
            )

        yield client, endpoint_id


def _format_container(c: dict) -> str:
    name = c.get("Names", ["/unknown"])[0].lstrip("/")
    state = c.get("State", "unknown")
    status = c.get("Status", "")
    image = c.get("Image", "unknown")
    container_id = c.get("Id", "")[:12]
    return f"{name:<30} {state:<10} {status:<25} {image:<40} {container_id}"


@tool
async def list_portainer_instances() -> str:
    """List all configured Portainer instances.

    Returns the names of available Portainer instances that can be targeted
    by other Portainer tools.
    """
    instances = get_settings().portainer.instances
    if not instances:
        return "No Portainer instances configured."
    lines = ["Configured Portainer instances:", ""]
    for name, inst in sorted(instances.items()):
        lines.append(f"  • {name} — {inst.base_url}")
    return "\n".join(lines)


@tool
async def list_containers(instance: str = "main", status_filter: str | None = None) -> str:
    """List Docker containers from a Portainer instance.

    Args:
        instance: Portainer instance name (default: "main").
        status_filter: Optional filter — 'running', 'stopped', or 'all' (default: all).
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.get(
                f"/api/endpoints/{eid}/docker/containers/json",
                params={"all": "true"},
            )
            resp.raise_for_status()
            containers = resp.json()
    except httpx.HTTPStatusError as e:
        return f"Portainer error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    if status_filter and status_filter != "all":
        containers = [c for c in containers if c.get("State") == status_filter]

    if not containers:
        return "No containers found."

    header = f"{'NAME':<30} {'STATE':<10} {'STATUS':<25} {'IMAGE':<40} {'ID'}"
    lines = [header, "-" * len(header)]
    for c in sorted(containers, key=lambda x: x.get("Names", [""])[0]):
        lines.append(_format_container(c))

    return "\n".join(lines)


@tool
async def get_container_details(container_id: str, instance: str = "main") -> str:
    """Get detailed information about a specific container.

    Args:
        container_id: Container ID (short or full) or container name.
        instance: Portainer instance name (default: "main").
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.get(f"/api/endpoints/{eid}/docker/containers/{container_id}/json")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Container '{container_id}' not found."
        return f"Portainer error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    info = {
        "Name": data.get("Name", "").lstrip("/"),
        "ID": data.get("Id", "")[:12],
        "Image": data.get("Config", {}).get("Image", "unknown"),
        "State": data.get("State", {}).get("Status", "unknown"),
        "Created": data.get("Created", ""),
        "RestartCount": data.get("RestartCount", 0),
        "Ports": data.get("NetworkSettings", {}).get("Ports", {}),
        "Mounts": [m.get("Source", "") for m in data.get("Mounts", [])],
    }
    return json.dumps(info, indent=2)


@tool
async def restart_container(container_id: str, instance: str = "main") -> str:
    """Restart a Docker container on a Portainer instance.

    Args:
        container_id: Container ID or name to restart.
        instance: Portainer instance name (default: "main").
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.post(
                f"/api/endpoints/{eid}/docker/containers/{container_id}/restart"
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Failed to restart: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    logger.info("container_restarted", container_id=container_id, instance=instance)
    return f"Container '{container_id}' restarted successfully on '{instance}'."


@tool
async def stop_container(container_id: str, instance: str = "main") -> str:
    """Stop a running Docker container on a Portainer instance.

    Args:
        container_id: Container ID or name to stop.
        instance: Portainer instance name (default: "main").
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.post(f"/api/endpoints/{eid}/docker/containers/{container_id}/stop")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Failed to stop: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    logger.info("container_stopped", container_id=container_id, instance=instance)
    return f"Container '{container_id}' stopped successfully on '{instance}'."


@tool
async def start_container(container_id: str, instance: str = "main") -> str:
    """Start a stopped Docker container on a Portainer instance.

    Args:
        container_id: Container ID or name to start.
        instance: Portainer instance name (default: "main").
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.post(f"/api/endpoints/{eid}/docker/containers/{container_id}/start")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 304:
            return f"Container '{container_id}' is already running."
        return f"Failed to start: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    logger.info("container_started", container_id=container_id, instance=instance)
    return f"Container '{container_id}' started successfully on '{instance}'."


@tool
async def get_container_logs(container_id: str, tail: int = 100, instance: str = "main") -> str:
    """Get recent logs from a Docker container on a Portainer instance.

    Args:
        container_id: Container ID or name.
        tail: Number of recent log lines to retrieve (default: 100).
        instance: Portainer instance name (default: "main").
    """
    try:
        async with _portainer_client(instance) as ctx:
            if isinstance(ctx, str):
                return ctx
            client, eid = ctx
            resp = await client.get(
                f"/api/endpoints/{eid}/docker/containers/{container_id}/logs",
                params={"stdout": "true", "stderr": "true", "tail": str(tail)},
            )
            resp.raise_for_status()
            logs = resp.text
    except httpx.HTTPStatusError as e:
        return f"Failed to get logs: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer ({instance}): {e}"

    if not logs.strip():
        return f"No recent logs for container '{container_id}'."

    cleaned_lines = []
    for line in logs.split("\n"):
        if len(line) > 8:
            cleaned_lines.append(line[8:] if ord(line[0]) in (0, 1, 2) else line)
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines[-tail:])
