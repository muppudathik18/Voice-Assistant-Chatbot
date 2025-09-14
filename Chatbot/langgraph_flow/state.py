# langgraph_flow/state.py
from typing import List, Dict, Any, Optional, TypedDict

class AgentState(TypedDict):
    user_query: str
    rewritten_query: str
    intent: str
    conversation_history: List[Dict[str, str]]
    answer: str
    session_id: str
    extracted_appointment_details: Optional[Dict[str, Any]]