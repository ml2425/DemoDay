"""
Document ingestion module.
Handles PDF parsing and document metadata extraction.
"""

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from pypdf import PdfReader
from dotenv import load_dotenv

from database.db_utils import connect, doc_exists_by_sha, insert_doc
from utils.runtime import get_config
from scripts.init_db import get_db_path
from services.pubmed_client import esearch, efetch_abstracts


@dataclass
class Doc:
    """Document data class."""
    doc_id: int
    sha256: str
    text: str
    source_kind: str = "LOCAL_PDF"


def sha256_bytes(data: bytes) -> str:
    """
    Compute SHA256 hash of bytes data.
    
    Args:
        data: Bytes data to hash
        
    Returns:
        SHA256 hex digest
    """
    return hashlib.sha256(data).hexdigest()


def clean_text(text: str) -> str:
    """
    Clean text by normalizing whitespace and removing excessive newlines.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def sentence_split(text: str) -> List[Dict[str, Any]]:
    """
    Split text into sentences using simple regex pattern.
    
    Args:
        text: Input text
        
    Returns:
        List of sentence dictionaries with 'text', 'sent_idx', 'char_start', 'char_end'
    """
    # Simple sentence splitting regex (period, exclamation, question mark)
    # Followed by space or end of string
    pattern = r'([.!?])\s+'
    
    sentences = []
    sent_idx = 0
    char_start = 0
    
    # Split on sentence boundaries
    parts = re.split(pattern, text)
    
    # Reconstruct sentences (pattern captures punctuation, so parts alternate)
    i = 0
    while i < len(parts):
        if i + 1 < len(parts):
            # Sentence + punctuation
            sent_text = parts[i] + parts[i + 1]
            char_end = char_start + len(sent_text)
            sentences.append({
                "text": sent_text.strip(),
                "sent_idx": sent_idx,
                "char_start": char_start,
                "char_end": char_end
            })
            char_start = char_end
            sent_idx += 1
            i += 2
        else:
            # Last fragment (no punctuation)
            if parts[i].strip():
                sent_text = parts[i]
                char_end = char_start + len(sent_text)
                sentences.append({
                    "text": sent_text.strip(),
                    "sent_idx": sent_idx,
                    "char_start": char_start,
                    "char_end": char_end
                })
            break
    
    return sentences


class Ingest:
    """Document ingestion class."""
    
    def __init__(self, db_path: str | None = None):
        """
        Initialize Ingest instance.
        
        Args:
            db_path: Optional database path. If None, reads from config or defaults to kg.sqlite
        """
        # Load environment variables
        load_dotenv()
        
        # Read config
        get_config()
        
        # Set db_path
        if db_path is None:
            db_path = str(get_db_path())
        self.db_path = db_path
    
    def from_pdf(self, paths: List[str]) -> List[Doc]:
        """
        Ingest PDF files, deduplicate by SHA256, and insert into database.
        
        Args:
            paths: List of PDF file paths
            
        Returns:
            List of Doc objects (existing or newly inserted)
        """
        conn = connect(self.db_path)
        docs = []
        
        try:
            for pdf_path in paths:
                file_path = Path(pdf_path)
                if not file_path.exists():
                    continue
                
                # Read PDF file as bytes
                with open(file_path, 'rb') as f:
                    pdf_bytes = f.read()
                
                # Compute SHA256 for deduplication
                sha256 = sha256_bytes(pdf_bytes)
                
                # Check if document already exists
                existing_doc_id = doc_exists_by_sha(conn, sha256)
                if existing_doc_id:
                    # Load existing document text (would need to retrieve from DB)
                    # For now, return doc_id and sha256
                    docs.append(Doc(
                        doc_id=existing_doc_id,
                        sha256=sha256,
                        text="",  # Would need to retrieve from storage if cached
                        source_kind="LOCAL_PDF"
                    ))
                    continue
                
                # Parse PDF
                reader = PdfReader(file_path)
                text_parts = []
                
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                # Concatenate and clean text
                full_text = "\n".join(text_parts)
                cleaned_text = clean_text(full_text)
                
                # Insert new document
                doc_id = insert_doc(
                    conn,
                    source_kind="LOCAL_PDF",
                    sha256=sha256
                )
                
                docs.append(Doc(
                    doc_id=doc_id,
                    sha256=sha256,
                    text=cleaned_text,
                    source_kind="LOCAL_PDF"
                ))
        
        finally:
            conn.close()
        
        return docs
    
    def from_pubmed(self, query: str, max_results: int = 100) -> List[Doc]:
        """
        Ingest documents from PubMed using search query.
        
        Searches PubMed, fetches abstracts, deduplicates by SHA256,
        and inserts into database.
        
        Args:
            query: PubMed search query string
            max_results: Maximum number of results to fetch
            
        Returns:
            List of Doc objects (existing or newly inserted)
        """
        # Search PubMed for PMIDs
        pmids = esearch(query, retmax=max_results)
        if not pmids:
            return []
        
        # Fetch abstracts
        abstracts = efetch_abstracts(pmids)
        if not abstracts:
            return []
        
        conn = connect(self.db_path)
        docs = []
        
        try:
            for abstract_data in abstracts:
                pmid = abstract_data.get("pmid", "")
                title = abstract_data.get("title", "")
                abstract_text = abstract_data.get("abstract", "")
                
                # Combine title and abstract for text content
                full_text = f"{title}\n\n{abstract_text}".strip()
                if not full_text:
                    continue
                
                # Compute SHA256 for deduplication
                text_bytes = full_text.encode('utf-8')
                sha256 = sha256_bytes(text_bytes)
                
                # Check if document already exists
                existing_doc_id = doc_exists_by_sha(conn, sha256)
                if existing_doc_id:
                    docs.append(Doc(
                        doc_id=existing_doc_id,
                        sha256=sha256,
                        text="",  # Would need to retrieve from storage if cached
                        source_kind="PUBMED_ABSTRACT"
                    ))
                    continue
                
                # Clean text
                cleaned_text = clean_text(full_text)
                
                # Insert new document
                doc_id = insert_doc(
                    conn,
                    source_kind="PUBMED_ABSTRACT",
                    sha256=sha256,
                    pmid=pmid
                )
                
                docs.append(Doc(
                    doc_id=doc_id,
                    sha256=sha256,
                    text=cleaned_text,
                    source_kind="PUBMED_ABSTRACT"
                ))
        
        finally:
            conn.close()
        
        return docs


__all__ = ["Doc", "Ingest", "sha256_bytes", "clean_text", "sentence_split"]

