from collections.abc import AsyncGenerator
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

logger = structlog.get_logger()


async def route_message(
    graph: CompiledStateGraph,
    message: str,
    *,
    user_id: str,
    user_role: str = "owner",
    thread_id: str,
    target_domain: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: dict[str, Any] = {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "user_role": user_role,
        "thread_id": thread_id,
        "active_agent": target_domain,
    }

    logger.info(
        "routing_message",
        user_id=user_id,
        thread_id=thread_id,
        target_domain=target_domain,
        message_preview=message[:100],
    )

    async for event in graph.astream(initial_state, config=config):
        yield event


async def resume_after_approval(
    graph: CompiledStateGraph,
    *,
    thread_id: str,
    approved: bool,
) -> AsyncGenerator[dict[str, Any], None]:
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("resuming_after_approval", thread_id=thread_id, approved=approved)

    async for event in graph.astream(Command(resume=approved), config=config):
        yield event


def extract_ai_response(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        for node_output in event.values():
            if isinstance(node_output, dict) and "messages" in node_output:
                for msg in reversed(node_output["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        return str(msg.content)
    return "No response generated."
