# langgraph_flow/nodes.py
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

# Import from other modules
from llm.helper import llm_helper
from llm.prompts import RAG_SYSTEM_PROMPT, APPOINTMENT_SYSTEM_PROMPT, CHITCHAT_SYSTEM_PROMPT, CLASSIFY_EXTRACT_PROMPT
from rag.retrieval import retrieve_top_k
from database.crud import load_history, append_history, get_agent_work_hours, get_agent_by_role, get_conflicting_appointments, create_appointment, get_upcoming_appointments
from langgraph_flow.state import AgentState

# For date parsing in appointment node
from dateutil import parser
from dateutil.relativedelta import relativedelta
from datetime import UTC # Ensure this is imported if used

# UTIL: Appointment Helpers (moved from main.py)
def parse_time_preference(text: str) -> Optional[datetime]:
    try:
        dt = parser.parse(text, fuzzy_with_tokens=True)[0]
        if not any(attr in text for attr in ['year', 'month', 'day', 'today', 'tomorrow', 'yesterday']):
            dt = dt.replace(year=datetime.now(UTC).year, month=datetime.now(UTC).month, day=datetime.now(UTC).day)
            if dt < datetime.now(UTC):
                dt += timedelta(days=1)
        return dt.replace(second=0, microsecond=0)
    except Exception:
        return None

def is_slot_available(agent_id: int, proposed_start_time: datetime, duration_minutes: int) -> bool:
    proposed_end_time = proposed_start_time + timedelta(minutes=duration_minutes)

    agent_hours = get_agent_work_hours(agent_id)
    if agent_hours:
        work_start_str, work_end_str = agent_hours
        work_start_dt = proposed_start_time.replace(hour=int(work_start_str.split(':')[0]), minute=int(work_start_str.split(':')[1]))
        work_end_dt = proposed_start_time.replace(hour=int(work_end_str.split(':')[0]), minute=int(work_end_str.split(':')[1]))

        if not (work_start_dt <= proposed_start_time < work_end_dt and work_start_dt < proposed_end_time <= work_end_dt):
            print(f"Slot {proposed_start_time} to {proposed_end_time} is outside agent's working hours ({work_start_dt} to {work_end_dt}).")
            return False

    conflicting_appointments = get_conflicting_appointments(agent_id, proposed_start_time.isoformat(), proposed_end_time.isoformat())
    if conflicting_appointments:
        print(f"Slot {proposed_start_time} to {proposed_end_time} conflicts with existing appointments.")
        return False
    return True

def find_available_agents(role: str, proposed_start_time: datetime, duration_minutes: int) -> List[Tuple[int, str]]:
    all_agents = get_agent_by_role(role)
    available_agents = []
    for agent_id, agent_name in all_agents:
        if is_slot_available(agent_id, proposed_start_time, duration_minutes):
            available_agents.append((agent_id, agent_name))
    return available_agents


# LangGraph Nodes
def node_rephrase_query(state: AgentState) -> Dict[str, Any]:
    user_query = state["user_query"]
    history = state["conversation_history"]
    try:
        rewritten = llm_helper.rephrase_query(user_query, history)
        print(f"[rephrase] Rewritten query: {rewritten}")
    except Exception as e:
        print(f"[rephrase] error: {e}")
        rewritten = user_query
    return {"rewritten_query": rewritten}

def node_classify_intent(state: AgentState) -> Dict[str, Any]:
    rewritten_query = state["rewritten_query"]
    extracted_appointment_details = None

    try:
        resp = llm_helper.client.chat.completions.create( # Use llm_helper.client
            model=llm_helper.chat_model, # Use llm_helper.chat_model
            messages=[{"role": "system", "content": CLASSIFY_EXTRACT_PROMPT},
                      {"role": "user", "content": f"User query: {rewritten_query}"}],
            max_tokens=200,
            temperature=0
        )
        llm_output = resp.choices[0].message.content.strip()
        print(f"[classify] Raw LLM output: {llm_output}")

        lines = llm_output.split('\n')
        intent = lines[0].strip().upper()

        if intent == "APPOINTMENT" and len(lines) > 1:
            try:
                json_str = "\n".join(lines[1:]).strip()
                extracted_appointment_details = json.loads(json_str)
                print(f"[classify] Extracted details: {extracted_appointment_details}")
            except json.JSONDecodeError:
                print(f"[classify] Warning: Could not parse JSON details for APPOINTMENT intent: {json_str}")
                extracted_appointment_details = None

        if "APPOINT" in intent:
            intent = "APPOINTMENT"
        elif "RAG" in intent:
            intent = "RAG"
        else:
            intent = "CHAT"

        print(f"[classify] Final Intent: {intent}")

    except Exception as e:
        print(f"[classify] error: {e}")
        intent = "RAG"
        extracted_appointment_details = None

    return {"intent": intent, "extracted_appointment_details": extracted_appointment_details}

def node_rag(state: AgentState) -> Dict[str, Any]:
    print("[RAG Node] Starting execution.")
    rewritten_query = state["rewritten_query"]
    history = state["conversation_history"]

    try:
        print("[RAG Node] Retrieving top K documents from Pinecone...")
        top = retrieve_top_k(rewritten_query) # k is already in config
        context_chunks = [f"Source: {url}\n{chunk[:2000]}" for score, chunk, url in top]
        print(f"[RAG Node] Found {len(context_chunks)} context chunks.")

        system_prompt = RAG_SYSTEM_PROMPT
        print("[RAG Node] Calling chat_with_context...")
        answer = llm_helper.chat_with_context(system_prompt, rewritten_query, context_chunks, history)
        print(f"[RAG Node] Answer generated: {answer[:100]}...")
        print("[RAG Node] Execution complete.")
        return {"answer": answer}
    except Exception as e:
        print(f"[RAG Node] ERROR during execution: {e}")
        return {"answer": f"An error occurred while processing your RAG query: {e}"}

def node_appointment(state: AgentState) -> Dict[str, Any]:
    rewritten_query = state["rewritten_query"]
    history = state["conversation_history"]
    extracted_details = state.get("extracted_appointment_details", {})

    answer = ""

    print(f"[Appointment Node] Received extracted details: {extracted_details}")

    action = extracted_details.get("action")
    appointment_type = extracted_details.get("appointment_type")
    customer_name = extracted_details.get("customer_name", "Guest")
    time_preference_str = extracted_details.get("time_preference")
    duration_minutes = extracted_details.get("duration_minutes", 30)
    agent_name_pref = extracted_details.get("agent_name")

    if action == "check_availability":
        print("[Appointment Node] Action: Check Availability.")
        rows = get_upcoming_appointments(limit=5)
        if not rows:
            answer = "No upcoming appointments are scheduled."
        else:
            lines = [f"{r[1]} at {r[0]}" for r in rows]
            answer = "Upcoming appointments:\n" + "\n".join(lines)
        print(f"[Appointment] Answer: {answer[:100]}...")
        return {"answer": answer}

    elif action == "book":
        print("[Appointment Node] Action: Book Appointment.")

        ADDITIONAL_APPOINTMENT_CONDITION = f"""To book an appointment, below are the necessary details,

            - appointment type - SALES or SERVICE
            - customer name
            - time preference

        Input details are given below. If any of the above details are not present, ask and get it from the user.

        **Input details:**
            - appointment_type: {appointment_type}
            - customer_name: {customer_name}
            - time_preference_str: {time_preference_str}
        """

        if not appointment_type or not time_preference_str or not customer_name:
            answer = llm_helper.chat_with_context(
                APPOINTMENT_SYSTEM_PROMPT,
                ADDITIONAL_APPOINTMENT_CONDITION,
                [], history
            )
            print("[Appointment Node] Missing appointment type.")
            return {"answer": answer}

        proposed_time = parse_time_preference(time_preference_str)
        if not proposed_time:
            answer = llm_helper.chat_with_context(
                APPOINTMENT_SYSTEM_PROMPT,
                f"I couldn't understand the date and time you mentioned. Could you please specify it clearly, for example, 'tomorrow at 2 PM' or 'next Monday at 10 AM'?",
                [], history
            )
            print("[Appointment Node] Failed to parse time preference.")
            return {"answer": answer}

        available_agents = find_available_agents(appointment_type, proposed_time, duration_minutes)

        selected_agent_id = None
        selected_agent_name = None

        if agent_name_pref:
            for agent_id, agent_name in available_agents:
                if agent_name_pref.lower() in agent_name.lower():
                    selected_agent_id = agent_id
                    selected_agent_name = agent_name
                    break
            if not selected_agent_id:
                answer = llm_helper.chat_with_context(
                    APPOINTMENT_SYSTEM_PROMPT,
                    f"I'm sorry, {agent_name_pref} is not available at {proposed_time.strftime('%I:%M %p')} on {proposed_time.strftime('%A, %B %d')}. There are no other agents available at that time either. Please try a different time.",
                    [], history
                )
                print(f"[Appointment Node] Preferred agent not available, no other agents.")
                return {"answer": answer}
        elif available_agents:
            selected_agent_id, selected_agent_name = available_agents[0]
        else:
            answer = llm_helper.chat_with_context(
                APPOINTMENT_SYSTEM_PROMPT,
                f"I'm sorry, I couldn't find any {appointment_type} agents available at {proposed_time.strftime('%I:%M %p')} on {proposed_time.strftime('%A, %B %d')}. Would you like to try a different time or day?",
                [], history
            )
            print(f"[Appointment Node] No agents available for {appointment_type} at {proposed_time}.")
            return {"answer": answer}

        try:
            create_appointment(selected_agent_id, customer_name, proposed_time.isoformat(), duration_minutes, appointment_type)
            answer = f"Great! Your {appointment_type} appointment with {selected_agent_name} on {proposed_time.strftime('%A, %B %d at %I:%M %p')} has been successfully booked for {customer_name}. We look forward to seeing you!"
            print(f"[Appointment Node] Appointment booked: {selected_agent_name} at {proposed_time}.")
        except Exception as e:
            answer = llm_helper.chat_with_context(
                APPOINTMENT_SYSTEM_PROMPT,
                f"I encountered an error while trying to book your appointment: {e}. Please try again.",
                [], history
            )
            print(f"[Appointment Node] Error during booking: {e}")

        print(f"[Appointment] Answer: {answer[:100]}...")
        return {"answer": answer}

    else: # If intent was APPOINTMENT but no action or details were extracted
        print("[Appointment Node] No clear action or details extracted for appointment.")
        answer = llm_helper.chat_with_context(
            APPOINTMENT_SYSTEM_PROMPT,
            f"Sure, I can help you with appointments. Please tell me your name and what type of appointment you're looking for (sales or service), and what date and time works best for you.",
            [], history
        )
        print(f"[Appointment] Answer: {answer[:100]}...")
        return {"answer": answer}


def node_chitchat(state: AgentState) -> Dict[str, Any]:
    print("[ChitChat Node] Starting execution.")
    rewritten_query = state["rewritten_query"]
    history = state["conversation_history"]
    system_prompt = CHITCHAT_SYSTEM_PROMPT
    answer = llm_helper.chat_with_context(system_prompt, rewritten_query, [], history)
    print(f"[ChitChat] Answer: {answer[:100]}...")
    print("[ChitChat Node] Execution complete.")
    return {"answer": answer}

def node_update_history(state: AgentState) -> Dict[str, Any]:
    print("[Update History Node] Starting execution.")
    session_id = state["session_id"]
    user_query = state["user_query"]
    answer = state["answer"]

    try:
        print(f"[Update History Node] Attempting to append user message: {user_query[:50]}...")
        append_history(session_id, "user", user_query)
        print("[Update History Node] User message appended successfully.")

        print(f"[Update History Node] Attempting to append assistant message: {answer[:50]}...")
        append_history(session_id, "assistant", answer)
        print("[Update History Node] Assistant message appended successfully.")

        print("[Update History Node] Attempting to reload conversation history...")
        updated_history = load_history(session_id, last_n=12)
        print(f"[Update History Node] History reloaded. Length: {len(updated_history)}")

        print("[Update History Node] All operations successful. About to return.")
        return {"conversation_history": updated_history}

    except Exception as e:
        print(f"[Update History Node] CRITICAL ERROR during execution: {e}")
        return {"conversation_history": state["conversation_history"], "error_in_history_update": str(e)}

