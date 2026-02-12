from pathlib import Path

import structlog
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from pan.agents.registry import get_all_agents
from pan.config.models import get_llm
from pan.orchestration.state import AgentState

logger = structlog.get_logger()

SUPERVISOR_PROMPT_PATH = Path(__file__).parent.parent / "config" / "prompts" / "supervisor.txt"


class RouterSchema(BaseModel):
    next: str
    reasoning: str


def _load_supervisor_prompt() -> str:
    return SUPERVISOR_PROMPT_PATH.read_text().strip()


def build_supervisor_graph(
    checkpointer: AsyncPostgresSaver,
) -> CompiledStateGraph:
    agents = get_all_agents()
    domain_names = list(agents.keys())
    supervisor_prompt = _load_supervisor_prompt()
    router_llm = get_llm("supervisor").with_structured_output(RouterSchema)

    async def supervisor_node(state: AgentState) -> Command:
        messages = [
            SystemMessage(content=supervisor_prompt),
            *state["messages"],
        ]

        # Direct routing when domain hint is set (from /ask <domain>)
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

        decision = await router_llm.ainvoke(messages)
        logger.info(
            "supervisor_routed",
            target=decision.next,
            reasoning=decision.reasoning,
        )

        if decision.next == "FINISH" or decision.next not in domain_names:
            return Command(
                goto=END,
                update={
                    "messages": [AIMessage(content=decision.reasoning)],
                    "active_agent": None,
                },
            )

        return Command(
            goto=decision.next,
            update={"active_agent": decision.next},
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
