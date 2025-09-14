# data_ingestion_service/scraper/core.py
import requests
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

def scrape_page(url: str) -> str:
    """Fetch page content and return visible text using BeautifulSoup."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # More targeted scraping: remove script, style, nav, footer, header elements
        for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
            script_or_style.extract()
        return soup.body.get_text(separator=' ', strip=True)
    except requests.exceptions.RequestException as e:
        print(f"Ingestion Service: Error fetching {url}: {e}")
        return ""

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)

def split_text_into_chunks(text: str) -> List[str]:
    """Splits raw text into smaller, manageable chunks."""
    return text_splitter.split_text(text)