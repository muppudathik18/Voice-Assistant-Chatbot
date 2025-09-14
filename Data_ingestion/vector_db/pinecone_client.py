# data_ingestion_service/vector_db/pinecone_client.py
from typing import List, Dict, Tuple
from pinecone import Pinecone, PodSpec
from openai import OpenAI
import numpy as np # Used for embeddings

# Import constants from config
from config import OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME, EMBED_MODEL

# Instantiate OpenAI client for embeddings
client = OpenAI(api_key=OPENAI_API_KEY)

# Pinecone Client Setup
pinecone_client = None
pinecone_index = None

try:
    pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
    pinecone_index = pinecone_client.Index(PINECONE_INDEX_NAME)
    print(f"Ingestion Service: Connected to Pinecone index '{PINECONE_INDEX_NAME}'.")
except Exception as e:
    print(f"Ingestion Service: Error connecting to Pinecone or initializing index: {e}")
    print("Please ensure PINECONE_API_KEY and PINECONE_ENVIRONMENT are correct, and the index exists or can be created.")
    exit(1)

def embed_text(text: str) -> List[float]:
    """Generates embeddings using OpenAI API."""
    try:
        res = client.embeddings.create(model=EMBED_MODEL, input=text)
        return res.data[0].embedding
    except Exception as e:
        print(f"Ingestion Service: Error generating OpenAI embedding: {e}")
        raise

def upsert_vectors_to_pinecone(url: str, chunks: List[str]):
    """Embeds text chunks and upserts them to Pinecone."""
    if pinecone_index is None:
        raise RuntimeError("Pinecone index not initialized. Cannot upsert vectors.")

    # Delete old vectors for this URL
    pinecone_index.delete(filter={"source": url})
    print(f"Ingestion Service: Deleted old vectors for {url} from Pinecone.")

    vectors_to_upsert = []
    batch_size = 100 # Pinecone recommended batch size

    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        vector_id = f"{url.replace('.', '_').replace('/', '_').replace(':', '_')}_{i}"
        vectors_to_upsert.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {"source": url, "chunk_index": i, "text": chunk}
        })

    if vectors_to_upsert:
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i+batch_size]
            pinecone_index.upsert(vectors=batch)
            print(f"Ingestion Service: Upserted {len(batch)} vectors for {url} (batch {i//batch_size + 1}).")
    else:
        print(f"Ingestion Service: No vectors to upsert for {url}")