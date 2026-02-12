from langgraph.graph.state import CompiledStateGraph

from pan.agents.base import create_domain_agent
from pan.agents.tech_chair.tools import (
    get_container_details,
    get_container_logs,
    list_containers,
    restart_container,
    start_container,
    stop_container,
)


def create_tech_chair_agent() -> CompiledStateGraph:
    tools = [
        list_containers,
        get_container_details,
        restart_container,
        stop_container,
        start_container,
        get_container_logs,
    ]
    return create_domain_agent(
        domain="tech_chair",
        tools=tools,
        prompt_file="tech_chair.txt",
    )
