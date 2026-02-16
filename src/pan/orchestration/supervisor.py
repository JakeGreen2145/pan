import re
from pathlib import Path

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from pan.agents.registry import get_all_agents
from pan.config.models import get_llm
from pan.orchestration.state import AgentState

logger = structlog.get_logger()

SUPERVISOR_PROMPT_PATH = Path(__file__).parent.parent / "config" / "prompts" / "supervisor.txt"

ROUTE_PATTERN = re.compile(r"ROUTE:\s*(\w+)", re.IGNORECASE)


def _load_supervisor_prompt() -> str:
    return SUPERVISOR_PROMPT_PATH.read_text().strip()


def _parse_route(text: str, valid_domains: list[str]) -> str | None:
    match = ROUTE_PATTERN.search(text)
    if match:
        target = match.group(1).lower()
        if target in valid_domains:
            return target
        if target == "finish":
            return "FINISH"

    text_lower = text.lower()
    for domain in valid_domains:
        if domain in text_lower:
            return domain

    return None


def build_supervisor_graph(
    checkpointer: AsyncPostgresSaver,
) -> CompiledStateGraph:
    agents = get_all_agents()
    domain_names = list(agents.keys())
    supervisor_prompt = _load_supervisor_prompt()
    router_llm = get_llm("supervisor")

    def _find_last_agent(state: AgentState) -> str | None:
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.name and msg.name in domain_names:
                return msg.name
        return None

    def _keyword_route(text: str) -> str | None:
        text_lower = text.lower()
        tech_keywords = (
            "container",
            "docker",
            "portainer",
            "vm",
            "proxmox",
            "truenas",
            "storage",
            "disk",
            "pool",
            "snapshot",
            "unifi",
            "network",
            "wifi",
            "ap",
            "switch",
            "gateway",
            "wan",
            "client",
            "device",
            "server",
            "restart",
            "stop",
            "start",
            "logs",
            "infrastructure",
            "homelab",
        )
        house_keywords = (
            "rent",
            "tenant",
            "lease",
            "payment",
            "late fee",
            "reminder",
            "unit",
            "landlord",
        )
        if any(kw in text_lower for kw in tech_keywords):
            return "tech_chair"
        if any(kw in text_lower for kw in house_keywords):
            return "house_manager"
        return None

    async def supervisor_node(state: AgentState) -> Command:
        last_message = state["messages"][-1] if state["messages"] else None
        agent_just_responded = (
            state.get("active_agent") is not None
            and isinstance(last_message, AIMessage)
            and not last_message.tool_calls
        )

        if agent_just_responded:
            logger.info(
                "supervisor_finishing",
                agent=state["active_agent"],
                reason="agent_responded",
            )
            return Command(
                goto=END,
                update={"active_agent": None},
            )

        if state.get("active_agent") and state["active_agent"] in domain_names:
            target = state["active_agent"]
            logger.info(
                "supervisor_direct_route",
                target=target,
                reason="explicit_domain_hint",
            )
            return Command(
                goto=target,
                update={"active_agent": target},
            )

        user_text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_text = str(msg.content)
                break

        target = None

        try:
            messages = [
                SystemMessage(content=supervisor_prompt),
                *state["messages"],
            ]
            response = await router_llm.ainvoke(messages)
            response_text = str(response.content)
            target = _parse_route(response_text, domain_names)
            if target and target != "FINISH":
                logger.info("supervisor_routed", target=target, method="llm")
        except Exception:
            logger.warning("supervisor_llm_failed", exc_info=True)

        if target is None:
            target = _keyword_route(user_text)
            if target:
                logger.info("supervisor_routed", target=target, method="keyword_fallback")

        if target is None:
            target = _find_last_agent(state)
            if target:
                logger.info("supervisor_routed", target=target, method="history_fallback")

        if target is None or target == "FINISH":
            return Command(
                goto=END,
                update={
                    "messages": [
                        AIMessage(
                            content="I'm not sure which agent should handle this. "
                            "Available agents: Tech Chair (infrastructure, containers, "
                            "VMs, storage, network) and House Manager (rent, tenants). "
                            "Try `/ask tech_chair <question>` or "
                            "`/ask house_manager <question>`."
                        )
                    ],
                    "active_agent": None,
                },
            )

        return Command(
            goto=target,
            update={"active_agent": target},
        )

    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor_node)

    for domain, agent_graph in agents.items():
        builder.add_node(domain, agent_graph)
        builder.add_edge(domain, "supervisor")

    builder.add_edge(START, "supervisor")

    graph = builder.compile(checkpointer=checkpointer)
    logger.info("supervisor_graph_built", domains=domain_names)
    return graph
