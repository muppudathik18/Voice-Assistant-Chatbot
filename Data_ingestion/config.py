# data_ingestion_service/config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- API Keys and Environment ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dealership-docs")

DEALERSHIP_URL = os.getenv("DEALERSHIP_URL", "https://www.stevenscreekchevy.com")

# --- Embedding Model ---
EMBED_MODEL = "text-embedding-3-small"

# --- Ingestion Interval (Informational for Cloud Run) ---
INGESTION_INTERVAL_MINUTES = 15

# --- Database Configuration ---
# For Cloud Run, DB_FILE will be set to /tmp/embeddings.db via env var
# For local, it will default to a file in the script's directory.
# Adjust path based on where this config.py is relative to your project root.
# Assuming this config.py is in data_ingestion_service/
DB_FILE = os.getenv("DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local_ingestion_db.db"))