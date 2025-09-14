# 🎙️ Voice Assistant Chatbot

The **Voice Assistant Chatbot** is a speech-enabled assistant that supports **voice input (STT)** and **voice output (TTS)**, leverages **Large Language Models (LLMs)** for intelligent responses and appointment booking, and uses **LangGraph** to structure conversation flows. The project is split into two main services contained in this repository:

- `Chatbot/` — the core assistant (LLM integration, LangGraph flows, runtime)
- `Data_ingestion/` — an ingestion service to scrape web pages, chunk documents, create embeddings, and persist vectors to a vector DB (e.g., Pinecone)

---

## ✅ High-level Features

- Voice-based Q&A and interactions
- Appointment booking with sales and service agents by checking their availability
- Modular LLM prompt & helper layer
- LangGraph-based conversational flow (nodes, graph, state)
- Data ingestion pipeline (web scraper → text splitter → embeddings → Pinecone)
- SQLite-based lightweight bookkeeping for scraped pages
- Docker-friendly setup for reproducible deployments

---

## 📂 Full Project Structure (accurate to repo root)

```
Voice_Assistant_Chatbot/
├── Chatbot/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── database/
│   │   └── crud.py
│   ├── langgraph_flow/
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   └── state.py
│   └── llm/
│       ├── helper.py
│       └── prompts.py
│
├── Data_ingestion/
│   ├── main.py                  # FastAPI ingestion service (endpoints + ingestion cycle)
│   ├── config.py                # ENV-driven configuration (Pinecone keys, URL, DB file)
│   ├── requirements.txt
│   ├── database/
│   │   └── crud.py              # sqlite bookkeeping: scraped_pages table, get/save methods
│   ├── scraper/
│   │   └── core.py              # page scraping + text cleaning + splitting
│   └── vector_db/
│       └── pinecone_client.py   # embedding creation and upsert to Pinecone
│
└── README.md                    # <-- this file
```

---

## 🛠️ Developer Setup (both services)

### Prerequisites

- Python 3.10+
- pip
- (Optional) Docker
- `.env` with API keys if using external services (OpenAI, Pinecone)

### Example `.env` (Data_ingestion/.env)

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pc-...
PINECONE_ENVIRONMENT=...
DB_FILE=/tmp/ingestion_db.db
```

Place `.env` in the `Data_ingestion/` directory (or set environment variables accordingly).

### Install dependencies per service

```bash
# For Chatbot
cd Voice_Assistant_Chatbot/Chatbot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# For Data_ingestion
cd ../Data_ingestion
python -m venv venv-ingest
source venv-ingest/bin/activate
pip install -r requirements.txt
```

---

## ▶️ Running the Data Ingestion Service (developer)

There are two ways to run the ingestion service:

**1) Quick-run (python)**

```bash
cd Voice_Assistant_Chatbot/Data_ingestion
python main.py
# main.py runs a FastAPI app and will call uvicorn internally when executed directly.
```

**2) Run with Uvicorn (recommended during development)**

```bash
cd Voice_Assistant_Chatbot/Data_ingestion
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

**Endpoints**

- `GET /ingest` — triggers a full ingestion cycle (scrape → chunk → embed → upsert)
- `GET /health` — returns health status and whether Pinecone index connection exists

---

## 🔁 Data Ingestion Code Flow (detailed)

This describes how the ingestion pipeline moves data from a website into the vector DB. File references below point to the `Data_ingestion/` module.

### 1. Entry point: `main.py`

- `perform_ingestion_cycle()` is the core orchestrator. It:

  1. reads target URLs (by default `DEALERSHIP_URL` from `config.py`),
  2. for each URL checks the last scraped timestamp using `database.crud.get_last_scraped_time(url)`,
  3. skips scraping if the page was scraped recently (controlled by `INGESTION_INTERVAL_MINUTES`),
  4. calls `scraper.core.scrape_page(url)` to obtain cleaned text,
  5. splits the text into manageable chunks (size/overlap can be adjusted inside `scraper.core`),
  6. calls `vector_db.pinecone_client.upsert_vectors_to_pinecone(url, chunks)` to embed & upsert vectors,
  7. saves or updates bookkeeping via `database.crud.save_scraped_page(url, raw_text)`.

- The FastAPI endpoint `GET /ingest` invokes `perform_ingestion_cycle()` so you can trigger ingestion on-demand or via a scheduler/hook.

### 2. Scraper: `scraper/core.py`

- `scrape_page(url: str) -> str`:
  - Uses `requests` to fetch HTML and `BeautifulSoup` to extract visible text (removes `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, etc.).
  - Cleans whitespace and filters out very short text fragments.
  - Uses `RecursiveCharacterTextSplitter` (from `langchain_text_splitters`) to chunk the document into smaller texts suitable for embedding.
  - Returns a list of text chunks (or raw text plus a chunk list depending on your configuration).

**Tip:** Tweak chunk size / overlap in `scraper/core.py` for downstream retrieval accuracy and cost tradeoffs.

### 3. Vector DB client: `vector_db/pinecone_client.py`

- `embed_text(text: str) -> List[float]`:
  - Calls your embedding model (OpenAI/other) to convert a text chunk into a numeric vector.
- `upsert_vectors_to_pinecone(url: str, chunks: List[str])`:
  - Initializes Pinecone client and index (if not already connected).
  - Deletes previous vectors for the same source (by filtering `{"source": url}`) to avoid duplicates.
  - Batches embeddings (recommended batch size 100) and calls `pinecone_index.upsert(vectors=...)` with metadata including source, chunk index and optionally the chunk text.
  - Metadata enables traceability and simpler retrieval later.

### 4. Database bookkeeping: `database/crud.py`

- Uses SQLite to store the table `scraped_pages(url, raw_text, scraped_at)`.
- `setup_db()` ensures table exists on startup.
- `get_last_scraped_time(url)` returns the last `scraped_at` timestamp for skipping re-scraping.
- `save_scraped_page(url, raw_text)` upserts the latest raw_text and timestamp for the URL.

---

## 🧪 Testing the pipeline locally

1. Ensure `.env` is set with a working OpenAI API key and Pinecone keys (or mock/embed logic for offline testing).
2. Start the ingestion service:
   ```bash
   cd Data_ingestion
   python main.py
   ```
3. Trigger ingestion (in a browser or curl):
   ```bash
   curl http://localhost:8080/ingest
   ```
4. Check logs for progress messages such as `Ingestion Service: Upserted ... vectors` or DB writes.

---

## 🛠️ Developer Notes & Extension Points (where to modify)

- Add more target URLs: Modify `main.py` to loop over a list of URLs or read from a database/CSV.
- Fine-tune chunking: `scraper/core.py` uses `RecursiveCharacterTextSplitter` — change `chunk_size` and `chunk_overlap` to tune performance & recall.
- Swap embeddings provider: `vector_db/pinecone_client.py` currently uses OpenAI client for embeddings; swap with another provider if needed.
- Vector index choices: Pinecone is implemented as an example — replace with FAISS/Weaviate/Vectara as needed.
- Add authentication: Protect `/ingest` endpoint via API key or other auth mechanism if exposing publicly.

---

## Chatbot Code Flow

The chatbot is orchestrated using **LangGraph** with a workflow of connected nodes. Each user query (text or voice) passes through the following steps:

1. **User Input**

   - Text via `/chat` endpoint.
   - Voice via `/voice_chat` → audio is transcribed to text.

2. **Node: `node_rephrase_query`**

   - Rewrites the user query into a standalone form (resolves pronouns and incomplete references).
   - Uses recent conversation history for context.

3. **Node: `node_classify_intent`**

   - Classifies the rewritten query into one of three intents:
     - **RAG** → factual question requiring document retrieval.
     - **APPOINTMENT** → booking or availability request.
     - **CHAT** → general small talk or casual conversation.
   - If intent is `APPOINTMENT`, also extracts appointment details (customer name, date/time, duration, type of service).

4. **Branching by Intent**

   - **RAG**
     - Calls `rag/retrieval.py` to embed the query and fetch top-k matching chunks from Pinecone.
     - Constructs context from retrieved chunks.
     - Calls the LLM with system + context + query → returns a grounded answer.
   - **APPOINTMENT**
     - Validates parsed details (time, customer name, duration).
     - Checks availability with database (`crud.py`).
     - If slot is free → creates appointment and confirms.
     - If missing/invalid info → asks clarifying question via LLM.
   - **CHAT**
     - Uses a lightweight chitchat system prompt.
     - Generates natural, conversational responses with no retrieval.

5. **Node: `node_update_history`**

   - Saves the assistant’s reply in the conversation history (SQLite).
   - Ensures continuity across multiple turns.

6. **Output**
   - Final assistant text response returned to client.
   - For `/voice_chat`, the text is also synthesized into speech and returned as audio.

---

**Summary:**  
The chatbot pipeline is:

`User Query → Rephrase → Classify Intent → (RAG | Appointment | Chat) → Update History → Response`

---

## ⚙️ Troubleshooting

- **Missing API keys / 401s:** Confirm `.env` variables are loaded and correct. `Data_ingestion/config.py` uses `dotenv.load_dotenv()`.
- **Pinecone errors:** Ensure the index exists in Pinecone console and `PINECONE_ENVIRONMENT` is correct.
- **No text found after scraping:** The scraper intentionally removes non-visible elements. Inspect `scraper/core.py` and try fetching the URL in a browser to see if content is rendered via JS (requires headless browser scraping if so).

---
