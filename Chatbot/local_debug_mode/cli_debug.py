# local_debug/cli_debug.py

import os
import sys
from datetime import datetime, timedelta, UTC
from typing import Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary components from your main application structure
from config import CHAT_MODEL, EMBED_MODEL, TTS_MODEL, TTS_VOICE, OPENAI_API_KEY
from database import crud
from llm.helper import llm_helper
from langgraph_flow.state import AgentState
from langgraph_flow.graph import build_graph

# Instantiate the LangGraph app
app_langgraph = build_graph()

def cli_loop_debug():
    session_id = f"session-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    print("Agent workflow CLI (Debug Mode). Type 'exit' to quit. Type '/scrape' to simulate data ingestion.")
    print("Note: This CLI uses the local SQLite DB and Pinecone. Ensure your .env is configured.")

    # Initialize DB for local debug
    crud.setup_db()

    current_conversation_history = crud.load_history(session_id, last_n=12)

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        if user_input.strip() == "/scrape":
            print("Scraping functionality is part of the separate data ingestion service. Please run that service or trigger its Cloud Run endpoint.")
            continue

        initial_state = AgentState(
            user_query=user_input,
            rewritten_query="",
            intent="",
            conversation_history=current_conversation_history,
            answer="",
            session_id=session_id,
            extracted_appointment_details=None
        )

        try:
            # Using invoke for simplicity in CLI, stream is more complex to display
            final_state_value = app_langgraph.invoke(initial_state)

            if final_state_value:
                assistant_answer = final_state_value["answer"]
                print(f"\nAssistant (Text): {assistant_answer}")

                current_conversation_history = final_state_value["conversation_history"]
            else:
                print("Error: Graph did not produce a final state.")

        except Exception as e:
            print(f"Error running workflow: {e}")
            # If you want to see the full traceback for debugging:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Ensure .env is loaded for local execution
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize Pinecone for local debug (it's called in rag/retrieval.py on import)
    # You might need to explicitly call initialize_pinecone_api_service() here
    # if it's not called on module import in rag/retrieval.py
    from rag.retrieval import initialize_pinecone_api_service
    try:
        initialize_pinecone_api_service()
        print("Local Pinecone initialized.")
    except Exception as e:
        print(f"Failed to initialize Pinecone for local debug: {e}")
        print("Please ensure your Pinecone API key and environment are correct in .env.")
        exit(1)

    cli_loop_debug()