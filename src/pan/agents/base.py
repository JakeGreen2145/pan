from pathlib import Path

import structlog
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from pan.config.models import get_llm

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def create_domain_agent(
    domain: str,
    tools: list[BaseTool],
    prompt_file: str | None = None,
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    if system_prompt is None and prompt_file is not None:
        prompt_path = PROMPTS_DIR / prompt_file
        system_prompt = prompt_path.read_text().strip()
    elif system_prompt is None:
        system_prompt = f"You are the {domain.replace('_', ' ').title()} agent."

    llm = get_llm(domain)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    logger.info("agent_created", domain=domain, tool_count=len(tools))
    return agent
