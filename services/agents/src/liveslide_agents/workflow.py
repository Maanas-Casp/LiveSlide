"""A deliberately small LangGraph risk gate: low scores stop; high scores draft."""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class RunState(TypedDict, total=False):
    risk_p: float
    decision: str


def assess(state: RunState) -> RunState:
    return {"decision": "prepare_draft" if state["risk_p"] >= 0.8 else "close_without_alert"}


def draft_gate(state: RunState) -> RunState:
    # Copy generation is template based in this basic build; dispatch is not possible here.
    return {"decision": "waiting_for_approval"}


def route(state: RunState) -> Literal["draft", "stop"]:
    return "draft" if state["decision"] == "prepare_draft" else "stop"


builder = StateGraph(RunState)
builder.add_node("assess", assess)
builder.add_node("draft", draft_gate)
builder.add_edge(START, "assess")
builder.add_conditional_edges("assess", route, {"draft": "draft", "stop": END})
builder.add_edge("draft", END)
risk_workflow = builder.compile()
