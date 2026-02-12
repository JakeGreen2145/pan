from langgraph.graph.state import CompiledStateGraph

from pan.agents.base import create_domain_agent
from pan.agents.house_manager.tools import (
    calculate_late_fees,
    check_rent_status,
    get_tenant_info,
    record_payment,
    send_rent_reminder,
)


def create_house_manager_agent() -> CompiledStateGraph:
    tools = [
        check_rent_status,
        get_tenant_info,
        calculate_late_fees,
        record_payment,
        send_rent_reminder,
    ]
    return create_domain_agent(
        domain="house_manager",
        tools=tools,
        prompt_file="house_manager.txt",
    )
