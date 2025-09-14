# data_ingestion_service/main.py

import os
from datetime import datetime, timedelta, UTC
from typing import List

# Import from your new modules
from config import DEALERSHIP_URL, INGESTION_INTERVAL_MINUTES
from database import crud as db_crud
from scraper import core as scraper_core
from vector_db import pinecone_client as pinecone_db

# FastAPI specific imports
from fastapi import FastAPI, Response, status, HTTPException
import uvicorn

# --- FastAPI Application ---
app = FastAPI(
    title="Dealership Data Ingestion Service",
    description="Periodically scrapes dealership website and updates Pinecone index.",
    version="1.0.0",
)


# --- Core Ingestion Logic ---
def perform_ingestion_cycle():
    pages_to_scrape = [
        DEALERSHIP_URL,
        f"{DEALERSHIP_URL}/service-parts-specials.html",
        f"{DEALERSHIP_URL}/ev-incentives",
        f"{DEALERSHIP_URL}/newspecials.html",
        f"{DEALERSHIP_URL}/usedspecials.html",
        f"{DEALERSHIP_URL}/black-friday-car-deals-san-jose",
        f"{DEALERSHIP_URL}/contactus.aspx", # Fixed missing comma
        f"{DEALERSHIP_URL}/fleet-vehicles",
        f"{DEALERSHIP_URL}/under-15k.html",
    ]
    print(f"\n--- Ingestion Cycle Started: {datetime.now(UTC)} ---")

    for url in pages_to_scrape:
        try:
            print(f"Ingestion Service: Processing {url}")
            last_scraped_at_str = db_crud.get_last_scraped_time(url)
            if last_scraped_at_str:
                last_scraped_dt = datetime.fromisoformat(last_scraped_at_str)
                if datetime.now(UTC) - last_scraped_dt < timedelta(minutes=INGESTION_INTERVAL_MINUTES):
                    print(f"Ingestion Service: {url} scraped recently, skipping.")
                    continue

            raw_text = scraper_core.scrape_page(url)
            if not raw_text.strip():
                print(f"Ingestion Service: No text found for {url}, skipping.")
                continue

            db_crud.save_scraped_page(url, raw_text)
            chunks = scraper_core.split_text_into_chunks(raw_text)
            print(f"Ingestion Service: {len(chunks)} chunks from {url}")

            pinecone_db.upsert_vectors_to_pinecone(url, chunks)

        except Exception as e:
            print(f"Ingestion Service: Failed to process {url}: {e}")

    print(f"--- Ingestion Cycle Finished: {datetime.now(UTC)} ---")


# --- FastAPI Endpoints ---
@app.get("/ingest")
async def trigger_ingestion():
    """
    Endpoint to trigger the data ingestion process.
    Designed to be called by Google Cloud Scheduler.
    """
    try:
        perform_ingestion_cycle()
        return {"message": "Data ingestion triggered and completed successfully."}
    except Exception as e:
        print(f"Error during ingestion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Data ingestion failed: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check Pinecone connection status from vector_db.pinecone_client
    return {"status": "ok", "pinecone_connected": pinecone_db.pinecone_index is not None}


# --- Main Entry Point for Uvicorn ---
if __name__ == "__main__":
    # Ensure DB is set up before Uvicorn runs
    db_crud.setup_db()
    uvicorn.run(app, host="0.0.0.0", port=8080)