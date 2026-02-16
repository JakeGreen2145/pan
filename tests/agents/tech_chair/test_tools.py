from unittest.mock import patch

import pytest
import respx

from pan.agents.tech_chair.portainer_tools import (
    get_container_details,
    get_container_logs,
    list_containers,
    restart_container,
)

PATCH_TARGET = "pan.agents.tech_chair.portainer_tools.get_settings"


@pytest.fixture
def portainer_mock(mock_portainer_response):
    with respx.mock(base_url="https://portainer.test:9443", assert_all_called=False) as mock:
        mock.get("/api/endpoints/1/docker/containers/json").respond(json=mock_portainer_response)
        mock.get("/api/endpoints/1/docker/containers/abc123def456/json").respond(
            json={
                "Name": "/nginx-proxy",
                "Id": "abc123def456",
                "Config": {"Image": "nginx:latest"},
                "State": {"Status": "running"},
                "Created": "2025-01-01T00:00:00Z",
                "RestartCount": 0,
                "NetworkSettings": {"Ports": {}},
                "Mounts": [],
            }
        )
        mock.post("/api/endpoints/1/docker/containers/abc123def456/restart").respond(
            status_code=204
        )
        mock.get("/api/endpoints/1/docker/containers/abc123def456/logs").respond(
            text="Line 1\nLine 2\nLine 3"
        )
        mock.get("/api/endpoints/1/docker/containers/nonexistent/json").respond(status_code=404)
        yield mock


async def test_list_containers(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await list_containers.ainvoke({"instance": "main", "status_filter": None})
        assert "nginx-proxy" in result
        assert "postgres-main" in result
        assert "stopped-service" in result


async def test_list_containers_filtered(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await list_containers.ainvoke({"instance": "main", "status_filter": "running"})
        assert "nginx-proxy" in result
        assert "stopped-service" not in result


async def test_get_container_details_found(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await get_container_details.ainvoke(
            {"container_id": "abc123def456", "instance": "main"}
        )
        assert "nginx-proxy" in result
        assert "nginx:latest" in result


async def test_get_container_details_not_found(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await get_container_details.ainvoke(
            {"container_id": "nonexistent", "instance": "main"}
        )
        assert "not found" in result.lower()


async def test_restart_container_success(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await restart_container.ainvoke(
            {"container_id": "abc123def456", "instance": "main"}
        )
        assert "restarted successfully" in result


async def test_get_container_logs_success(portainer_mock, test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await get_container_logs.ainvoke(
            {"container_id": "abc123def456", "tail": 50, "instance": "main"}
        )
        assert "Line 1" in result


async def test_unknown_instance(test_settings):
    with patch(PATCH_TARGET, return_value=test_settings):
        result = await list_containers.ainvoke({"instance": "nonexistent"})
        assert "Unknown Portainer instance" in result
        assert "main" in result
