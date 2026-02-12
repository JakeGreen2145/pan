import structlog
from langgraph.graph.state import CompiledStateGraph

from pan.exceptions import AgentNotFoundError

logger = structlog.get_logger()

_registry: dict[str, CompiledStateGraph] = {}


def register_agent(domain: str, graph: CompiledStateGraph) -> None:
    _registry[domain] = graph
    logger.info("agent_registered", domain=domain)


def get_agent(domain: str) -> CompiledStateGraph:
    if domain not in _registry:
        raise AgentNotFoundError(domain)
    return _registry[domain]


def list_domains() -> list[str]:
    return list(_registry.keys())


def get_all_agents() -> dict[str, CompiledStateGraph]:
    return dict(_registry)


async def init_agents() -> None:
    from pan.agents.house_manager import create_house_manager_agent
    from pan.agents.tech_chair import create_tech_chair_agent

    register_agent("tech_chair", create_tech_chair_agent())
    register_agent("house_manager", create_house_manager_agent())

    logger.info("all_agents_initialized", domains=list_domains())
