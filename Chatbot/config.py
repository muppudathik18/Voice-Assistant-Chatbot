# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- API Keys and Environment ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dealership-docs") # Allow override

DEALERSHIP_URL = os.getenv("DEALERSHIP_URL", "https://www.stevenscreekchevy.com")

# --- Model Configuration ---
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 3

TTS_MODEL = "tts-1"
TTS_VOICE = "alloy"

# --- Database Configuration ---
# For Cloud Run, DB_FILE will be set to /tmp/embeddings.db via env var
# For local, it will default to a file in the script's directory
DB_FILE = os.getenv("DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local_embeddings.db"))

# --- Debug Flag ---
DEBUG_MODE = False 