# rag/retrieval.py
from typing import List, Tuple
from pinecone import Pinecone
from openai import OpenAI

# Import constants from config
from config import PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME, EMBED_MODEL, TOP_K, OPENAI_API_KEY

# Instantiate OpenAI client for embeddings
client = OpenAI(api_key=OPENAI_API_KEY)

# Pinecone Client Setup (API Service)
pinecone_client = None
pinecone_index = None

def initialize_pinecone_api_service():
    """Initializes Pinecone client and index for the API service."""
    global pinecone_client, pinecone_index
    try:
        pinecone_client = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
        pinecone_index = pinecone_client.Index(PINECONE_INDEX_NAME)
        print(f"API Service: Connected to Pinecone index '{PINECONE_INDEX_NAME}'.")
    except Exception as e:
        print(f"API Service: Error connecting to Pinecone or getting index: {e}")
        raise RuntimeError(f"Failed to initialize Pinecone for API service: {e}")

def embed_text(text: str) -> List[float]:
    """Generates embeddings using OpenAI API."""
    try:
        res = client.embeddings.create(model=EMBED_MODEL, input=text)
        return res.data[0].embedding
    except Exception as e:
        print(f"API Service: Error generating OpenAI embedding: {e}")
        raise

def retrieve_top_k(query: str, k: int = TOP_K) -> List[Tuple[float, str, str]]:
    """Return list[(score, chunk, url)] by querying Pinecone."""
    if pinecone_index is None:
        print("[Retrieval] Pinecone index is not initialized.")
        return []

    query_embedding = embed_text(query) # Get embedding for the query

    # Query Pinecone
    query_results = pinecone_index.query(
        vector=query_embedding,
        top_k=k,
        include_metadata=True # Ensure metadata is returned
    )

    scored = []
    for match in query_results.matches:
        score = match.score
        metadata = match.metadata
        chunk = metadata.get('text', '') # Retrieve the original text from metadata
        url = metadata.get('source', 'unknown')
        scored.append((score, chunk, url))

    return scored