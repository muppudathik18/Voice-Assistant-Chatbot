# langgraph_flow/graph.py
from langgraph.graph import StateGraph, END

# Import nodes and state
from langgraph_flow.nodes import (
    node_rephrase_query,
    node_classify_intent,
    node_rag,
    node_appointment,
    node_chitchat,
    node_update_history
)
from langgraph_flow.state import AgentState

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("rephrase", node_rephrase_query)
    workflow.add_node("classify", node_classify_intent)
    workflow.add_node("rag", node_rag)
    workflow.add_node("appointment", node_appointment)
    workflow.add_node("chitchat", node_chitchat)
    workflow.add_node("update_history", node_update_history)

    workflow.set_entry_point("rephrase")

    workflow.add_edge("rephrase", "classify")

    workflow.add_conditional_edges(
        "classify",
        lambda state: state["intent"],
        {
            "RAG": "rag",
            "APPOINTMENT": "appointment",
            "CHAT": "chitchat",
        },
    )

    workflow.add_edge("rag", "update_history")
    workflow.add_edge("appointment", "update_history")
    workflow.add_edge("chitchat", "update_history")

    workflow.add_edge("update_history", END)

    return workflow.compile()