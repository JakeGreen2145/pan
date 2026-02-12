from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from pan.config.settings import get_settings


@dataclass(frozen=True)
class AgentModelConfig:
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4096


DEFAULT_MODEL = AgentModelConfig(
    model_name="anthropic/claude-sonnet-4-20250514",
    temperature=0.7,
    max_tokens=4096,
)

AGENT_MODELS: dict[str, AgentModelConfig] = {
    "supervisor": AgentModelConfig(
        model_name="anthropic/claude-sonnet-4-20250514",
        temperature=0.0,
        max_tokens=1024,
    ),
    "tech_chair": AgentModelConfig(
        model_name="anthropic/claude-sonnet-4-20250514",
        temperature=0.3,
        max_tokens=4096,
    ),
    "house_manager": AgentModelConfig(
        model_name="anthropic/claude-sonnet-4-20250514",
        temperature=0.5,
        max_tokens=4096,
    ),
}


def get_llm(domain: str) -> ChatOpenAI:
    settings = get_settings()
    config = AGENT_MODELS.get(domain, DEFAULT_MODEL)

    return ChatOpenAI(
        model=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=settings.openrouter.api_key.get_secret_value(),
        base_url=settings.openrouter.base_url,
    )
