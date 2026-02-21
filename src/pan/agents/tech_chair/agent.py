from langgraph.graph.state import CompiledStateGraph

from pan.agents.base import create_domain_agent
from pan.agents.tech_chair.portainer_tools import (
    get_container_details,
    get_container_logs,
    list_containers,
    list_portainer_instances,
    restart_container,
    start_container,
    stop_container,
)
from pan.agents.tech_chair.proxmox_tools import (
    get_node_status,
    get_vm_status,
    list_vms,
    reboot_vm,
    start_vm,
    stop_vm,
)
from pan.agents.tech_chair.truenas_tools import (
    get_disk_health,
    get_storage_summary,
    get_system_info,
    get_truenas_alerts,
    list_datasets,
    list_snapshots,
)
from pan.agents.tech_chair.unifi_tools import (
    get_network_health,
    get_wan_info,
    list_network_clients,
    list_network_devices,
    list_networks,
)


def create_tech_chair_agent() -> CompiledStateGraph:
    tools = [
        list_portainer_instances,
        list_containers,
        get_container_details,
        restart_container,
        stop_container,
        start_container,
        get_container_logs,
        list_vms,
        get_vm_status,
        start_vm,
        stop_vm,
        reboot_vm,
        get_node_status,
        get_storage_summary,
        list_datasets,
        list_snapshots,
        get_disk_health,
        get_truenas_alerts,
        get_system_info,
        get_network_health,
        list_network_devices,
        list_network_clients,
        get_wan_info,
        list_networks,
    ]
    return create_domain_agent(
        domain="tech_chair",
        tools=tools,
        prompt_file="tech_chair.txt",
    )
