"""Node 1: Extract text from PDF or PubMed source."""

from typing import Dict, Any
from pathlib import Path
from sources.pdf_handler import process_pdf, get_pdf_title
from services.pubmed_client import search_and_fetch
from database.db_utils import insert_source, get_source


def extract_text_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract text from PDF or PubMed source.
    
    Expected state keys:
        - source_type: "PDF" or "PUBMED"
        - pdf_path: Path to PDF (if PDF)
        - keywords: Search keywords (if PubMed)
        - max_results: Max PubMed results (if PubMed)
    
    Updates state with:
        - source_id: "UUID:..." or "PMID:..."
        - full_text: Extracted text
        - metadata: Source metadata (title, authors, etc.)
    """
    source_type = state.get("source_type", "").upper()
    
    if source_type == "PDF":
        pdf_path = Path(state["pdf_path"])
        
        # Process PDF
        pdf_data = process_pdf(pdf_path)
        full_uuid = pdf_data["full_uuid"]
        text = pdf_data["text"]
        original_filename = pdf_data["original_filename"]
        
        # Get title if available
        title = get_pdf_title(pdf_path)
        
        source_id = f"UUID:{full_uuid}"
        metadata = {
            "filename": original_filename,
            "title": title,
            "prefix": pdf_data["prefix"]
        }
        
        # Check if already exists
        from database.db_utils import connect
        conn = connect()
        existing = get_source(conn, source_id)
        
        if existing:
            print(f"[INFO] Source {source_id} already exists, skipping insertion")
            state["source_id"] = source_id
            state["full_text"] = existing["full_text"]
            state["metadata"] = metadata
            conn.close()
            return state
        
        # Insert source
        insert_source(conn, source_id, "LOCAL_PDF", text, metadata)
        conn.close()
        
        state["source_id"] = source_id
        state["full_text"] = text
        state["metadata"] = metadata
        
    elif source_type == "PUBMED":
        keywords = state.get("keywords", "")
        max_results = state.get("max_results", 5)
        
        # Search and fetch abstracts
        articles = search_and_fetch(keywords, max_results)
        
        if not articles:
            raise ValueError(f"No PubMed results found for: {keywords}")
        
        # Process first article (can extend to multiple later)
        article = articles[0]
        pmid = article["pmid"]
        source_id = f"PMID:{pmid}"
        
        # Combine title + abstract as full_text
        full_text = f"{article['title']}\n\n{article['abstract']}"
        
        metadata = {
            "title": article["title"],
            "authors": article["authors"],
            "doi": article.get("doi")
        }
        
        # Check if already exists
        from database.db_utils import connect
        conn = connect()
        existing = get_source(conn, source_id)
        
        if existing:
            print(f"[INFO] Source {source_id} already exists, skipping insertion")
            state["source_id"] = source_id
            state["full_text"] = existing["full_text"]
            state["metadata"] = metadata
            conn.close()
            return state
        
        # Insert source
        insert_source(conn, source_id, "PUBMED", full_text, metadata)
        conn.close()
        
        state["source_id"] = source_id
        state["full_text"] = full_text
        state["metadata"] = metadata
        
    else:
        raise ValueError(f"Unknown source_type: {source_type}")
    
    print(f"[OK] Extracted text from {source_type} source: {source_id}")
    return state

