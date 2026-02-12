import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from langchain_core.tools import tool

from pan.config.settings import get_settings
from pan.exceptions import PortainerError

logger = structlog.get_logger()

_cached_endpoint_id: int | None = None


@asynccontextmanager
async def _portainer_client() -> AsyncGenerator[tuple[httpx.AsyncClient, int], None]:
    global _cached_endpoint_id
    settings = get_settings().portainer

    headers = {"X-API-Key": settings.api_key.get_secret_value()}

    async with httpx.AsyncClient(
        base_url=settings.base_url,
        headers=headers,
        verify=settings.verify_ssl,
        timeout=30.0,
    ) as client:
        if settings.endpoint_id is not None:
            endpoint_id = settings.endpoint_id
        elif _cached_endpoint_id is not None:
            endpoint_id = _cached_endpoint_id
        else:
            resp = await client.get("/api/endpoints")
            resp.raise_for_status()
            endpoints = resp.json()
            if not endpoints:
                raise PortainerError(500, "No Portainer endpoints found")
            endpoint_id = endpoints[0]["Id"]
            _cached_endpoint_id = endpoint_id
            logger.info("portainer_endpoint_discovered", endpoint_id=endpoint_id)

        yield client, endpoint_id


def _format_container(c: dict) -> str:
    name = c.get("Names", ["/unknown"])[0].lstrip("/")
    state = c.get("State", "unknown")
    status = c.get("Status", "")
    image = c.get("Image", "unknown")
    container_id = c.get("Id", "")[:12]
    return f"{name:<30} {state:<10} {status:<25} {image:<40} {container_id}"


@tool
async def list_containers(status_filter: str | None = None) -> str:
    """List Docker containers from Portainer.

    Args:
        status_filter: Optional filter — 'running', 'stopped', or 'all' (default: all).
    """
    try:
        async with _portainer_client() as (client, eid):
            params = {"all": "true"}
            resp = await client.get(
                f"/api/endpoints/{eid}/docker/containers/json",
                params=params,
            )
            resp.raise_for_status()
            containers = resp.json()
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

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
async def get_container_details(container_id: str) -> str:
    """Get detailed information about a specific container.

    Args:
        container_id: Container ID (short or full) or container name.
    """
    try:
        async with _portainer_client() as (client, eid):
            resp = await client.get(f"/api/endpoints/{eid}/docker/containers/{container_id}/json")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Container '{container_id}' not found."
        return f"Portainer error: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

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
async def restart_container(container_id: str) -> str:
    """Restart a Docker container.

    Args:
        container_id: Container ID or name to restart.
    """
    try:
        async with _portainer_client() as (client, eid):
            resp = await client.post(
                f"/api/endpoints/{eid}/docker/containers/{container_id}/restart"
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Failed to restart: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

    logger.info("container_restarted", container_id=container_id)
    return f"Container '{container_id}' restarted successfully."


@tool
async def stop_container(container_id: str) -> str:
    """Stop a running Docker container.

    Args:
        container_id: Container ID or name to stop.
    """
    try:
        async with _portainer_client() as (client, eid):
            resp = await client.post(f"/api/endpoints/{eid}/docker/containers/{container_id}/stop")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Failed to stop: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

    logger.info("container_stopped", container_id=container_id)
    return f"Container '{container_id}' stopped successfully."


@tool
async def start_container(container_id: str) -> str:
    """Start a stopped Docker container.

    Args:
        container_id: Container ID or name to start.
    """
    try:
        async with _portainer_client() as (client, eid):
            resp = await client.post(f"/api/endpoints/{eid}/docker/containers/{container_id}/start")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 304:
            return f"Container '{container_id}' is already running."
        return f"Failed to start: {e.response.status_code} — {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

    logger.info("container_started", container_id=container_id)
    return f"Container '{container_id}' started successfully."


@tool
async def get_container_logs(container_id: str, tail: int = 100) -> str:
    """Get recent logs from a Docker container.

    Args:
        container_id: Container ID or name.
        tail: Number of recent log lines to retrieve (default: 100).
    """
    try:
        async with _portainer_client() as (client, eid):
            resp = await client.get(
                f"/api/endpoints/{eid}/docker/containers/{container_id}/logs",
                params={"stdout": "true", "stderr": "true", "tail": str(tail)},
            )
            resp.raise_for_status()
            logs = resp.text
    except httpx.HTTPStatusError as e:
        return f"Failed to get logs: {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Error connecting to Portainer: {e}"

    if not logs.strip():
        return f"No recent logs for container '{container_id}'."

    # Strip Docker stream headers (8-byte prefix per line)
    cleaned_lines = []
    for line in logs.split("\n"):
        if len(line) > 8:
            cleaned_lines.append(line[8:] if ord(line[0]) in (0, 1, 2) else line)
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines[-tail:])
