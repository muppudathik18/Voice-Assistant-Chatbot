# main.py (The new, refactored main entry point)

import os
import json
import sqlite3 # Still needed for conn/cur setup, or move that to database/crud.py
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Tuple, TypedDict, Optional

# Import from your new modules
from config import (
    OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME,
    DEALERSHIP_URL, DB_FILE, EMBED_MODEL, CHAT_MODEL, TOP_K, TTS_MODEL, TTS_VOICE,
    DEBUG_MODE
)
from database import crud # Import the crud module
from llm.helper import llm_helper # Import the instantiated LLMHelper
from rag.retrieval import initialize_pinecone_api_service # Import Pinecone init for API service
from langgraph_flow.state import AgentState # Import AgentState
from langgraph_flow.graph import build_graph # Import the graph builder

# FastAPI specific imports
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Other necessary imports
import io
import uuid # Not used in this version, can remove if not needed
from dateutil import parser # Used in nodes, but not directly in main.py anymore
from dateutil.relativedelta import relativedelta # Used in nodes, but not directly in main.py anymore
from openai import OpenAI # Used in llm.helper and rag.retrieval, not directly here

# --- Global Setup (Minimal) ---
# DB Connection (still here for now, could be moved to crud.py and managed via FastAPI dependencies)
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
crud.setup_db() # Call the setup function from crud.py

# Compile the LangGraph
app_langgraph = build_graph()

# --- FastAPI App Definition ---
app_fastapi = FastAPI(
    title="Dealership Voice Chatbot API",
    description="API for Stevens Creek Chevrolet Voice Chatbot with RAG, Appointment, and ChitChat capabilities.",
    version="1.0.0",
)

app_fastapi.mount("/static", StaticFiles(directory="static"), name="static")

# --- FastAPI Event Handlers ---
@app_fastapi.on_event("startup")
async def startup_event():
    print("FastAPI app startup: Initializing Pinecone for API service...")
    try:
        initialize_pinecone_api_service()
        print("FastAPI app startup: Pinecone initialized successfully.")
    except Exception as e:
        print(f"FastAPI app startup: CRITICAL ERROR during Pinecone initialization: {e}")
        raise HTTPException(status_code=500, detail=f"API service failed to start due to Pinecone error: {e}")

# --- FastAPI Endpoints ---

# Pydantic Models for Endpoints
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    response: str

@app_fastapi.get("/", response_class=HTMLResponse)
async def get_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app_fastapi.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request_body: ChatRequest):
    user_query = request_body.query
    session_id = request_body.session_id
    if not session_id:
        session_id = f"session-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    print(f"API Service: Received text query for session {session_id}: {user_query}")

    current_conversation_history = crud.load_history(session_id, last_n=12) # Use crud.load_history

    initial_state = AgentState(
        user_query=user_query,
        rewritten_query="",
        intent="",
        conversation_history=current_conversation_history,
        answer="",
        session_id=session_id,
        extracted_appointment_details=None
    )

    try:
        final_state_value = app_langgraph.invoke(initial_state)

        if final_state_value:
            assistant_answer = final_state_value["answer"]
            print(f"API Service: Assistant text response for session {session_id}: {assistant_answer[:100]}...")
            return ChatResponse(session_id=session_id, response=assistant_answer)
        else:
            print(f"API Service: Error: Graph did not produce a final state for session {session_id}.")
            raise HTTPException(status_code=500, detail="Internal server error: Graph did not complete")

    except Exception as e:
        print(f"API Service: Error processing text chat request for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app_fastapi.post("/voice_chat")
async def voice_chat_endpoint(
    audio_file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    if not session_id:
        session_id = f"session-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    print(f"API Service: Received voice query for session {session_id}")

    user_audio_bytes = await audio_file.read()
    user_audio_buffer = io.BytesIO(user_audio_bytes)
    user_audio_buffer.name = audio_file.filename

    try:
        # Use client from llm.helper or rag.retrieval if needed, or pass it
        # For now, let's assume client is globally available from rag.retrieval
        from rag.retrieval import client as openai_client_for_stt # Import the client from rag.retrieval

        transcript = openai_client_for_stt.audio.transcriptions.create(
            model="whisper-1",
            file=user_audio_buffer
        )
        user_text = transcript.text
        print(f"API Service: User (STT): {user_text}")
    except Exception as e:
        print(f"API Service: STT Error: {e}")
        raise HTTPException(status_code=500, detail=f"Speech-to-Text failed: {e}")

    current_conversation_history = crud.load_history(session_id, last_n=12) # Use crud.load_history

    initial_state = AgentState(
        user_query=user_text,
        rewritten_query="",
        intent="",
        conversation_history=current_conversation_history,
        answer="",
        session_id=session_id,
        extracted_appointment_details=None
    )

    try:
        final_state_value = app_langgraph.invoke(initial_state)

        if final_state_value:
            assistant_answer = final_state_value["answer"]
            print(f"API Service: Assistant (Text): {assistant_answer[:100]}...")
        else:
            print(f"API Service: Error: Graph did not produce a final state for session {session_id}.")
            raise HTTPException(status_code=500, detail="Internal server error: Graph did not complete")

    except Exception as e:
        print(f"API Service: Error processing voice chat request for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Use client from llm.helper or rag.retrieval for TTS
        from rag.retrieval import client as openai_client_for_tts # Import the client from rag.retrieval
        from config import TTS_MODEL, TTS_VOICE # Import TTS config

        speech_response = openai_client_for_tts.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=assistant_answer
        )
        return StreamingResponse(speech_response.iter_bytes(1024), media_type="audio/mpeg")
    except Exception as e:
        print(f"API Service: TTS Error: {e}")
        raise HTTPException(status_code=500, detail=f"Text-to-Speech failed: {e}")

@app_fastapi.get("/health")
async def health_check():
    # Check Pinecone connection status from rag.retrieval
    from rag.retrieval import pinecone_index as rag_pinecone_index
    return {"status": "ok", "pinecone_connected": rag_pinecone_index is not None}


# --- Main Entry Point for Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    print("Starting API Service with Uvicorn...")
    uvicorn.run(app_fastapi, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))