"""
Entity and concept database utilities.
Handles concept upserts and entity insertions.
"""

import sqlite3
from typing import Optional


def upsert_concept(conn: sqlite3.Connection, name: str, category: str, llm_conf: float) -> int:
    """
    Upsert a canonical concept (insert or update if exists).
    
    Uses canonical_name as unique identifier - if concept with same name exists,
    updates it; otherwise inserts new concept.
    
    Args:
        conn: Database connection
        name: Canonical concept name
        category: Semantic category (DISORDER, FINDING, PROCEDURE, DRUG, INVESTIGATION, MICROBE)
        llm_conf: LLM confidence score
        
    Returns:
        canonical_id of the concept
    """
    cursor = conn.cursor()
    
    # Check if concept exists
    cursor.execute(
        "SELECT canonical_id FROM concepts WHERE canonical_name = ?",
        (name,)
    )
    row = cursor.fetchone()
    
    if row:
        # Update existing concept
        canonical_id = row[0]
        cursor.execute(
            """
            UPDATE concepts 
            SET semantic_category = ?, llm_conf = ?
            WHERE canonical_id = ?
            """,
            (category, llm_conf, canonical_id)
        )
    else:
        # Insert new concept
        cursor.execute(
            """
            INSERT INTO concepts (canonical_name, semantic_category, llm_conf)
            VALUES (?, ?, ?)
            """,
            (name, category, llm_conf)
        )
        canonical_id = cursor.lastrowid
    
    conn.commit()
    return canonical_id


def insert_entity(
    conn: sqlite3.Connection,
    canonical_id: int,
    doc_id: int,
    sent_idx: int,
    char_start: int,
    char_end: int,
    span_text: str
) -> int:
    """
    Insert an entity mention into the entities table.
    
    Args:
        conn: Database connection
        canonical_id: Reference to concepts.canonical_id
        doc_id: Reference to docs.doc_id
        sent_idx: Sentence index (0-based)
        char_start: Character start position in document
        char_end: Character end position in document
        span_text: Original span text
        
    Returns:
        entity_id of inserted entity
    """
    cursor = conn.execute(
        """
        INSERT INTO entities (canonical_id, doc_id, sent_idx, char_start, char_end, span_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (canonical_id, doc_id, sent_idx, char_start, char_end, span_text)
    )
    conn.commit()
    return cursor.lastrowid

