"""
Database utility functions.
Handles connections and document operations.
"""

import sqlite3
from pathlib import Path
from typing import Optional


def connect(db_path: str = "kg.sqlite") -> sqlite3.Connection:
    """
    Connect to SQLite database with FK and WAL enabled.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        SQLite connection with foreign keys and WAL mode enabled
    """
    # Ensure parent directory exists
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Enable WAL mode for concurrent reads during writes
    conn.execute("PRAGMA journal_mode = WAL")
    
    return conn


def doc_exists_by_sha(conn: sqlite3.Connection, sha256: str) -> Optional[int]:
    """
    Check if a document exists by SHA256 hash.
    
    Args:
        conn: Database connection
        sha256: SHA256 hash of document content
        
    Returns:
        doc_id if exists, None otherwise
    """
    cursor = conn.execute(
        "SELECT doc_id FROM docs WHERE sha256 = ?",
        (sha256,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def insert_doc(
    conn: sqlite3.Connection,
    source_kind: str,
    sha256: str,
    pmid: Optional[str] = None,
    doi: Optional[str] = None,
    url: Optional[str] = None
) -> int:
    """
    Insert a new document into the docs table.
    
    Args:
        conn: Database connection
        source_kind: Source type ('LOCAL_PDF', 'PUBMED_ABSTRACT', 'PMC_FULLTEXT')
        sha256: SHA256 hash of document content
        pmid: Optional PubMed ID
        doi: Optional DOI
        url: Optional URL
        
    Returns:
        doc_id of inserted document
        
    Raises:
        sqlite3.IntegrityError: If sha256 already exists
    """
    cursor = conn.execute(
        """
        INSERT INTO docs (source_kind, sha256, pmid, doi, url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source_kind, sha256, pmid, doi, url)
    )
    conn.commit()
    return cursor.lastrowid

