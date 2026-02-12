from langgraph.graph import MessagesState


class AgentState(MessagesState):
    active_agent: str | None = None
    user_id: str | None = None
    user_role: str = "owner"
    thread_id: str | None = None
