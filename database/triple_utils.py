"""
Triple and evidence database utilities.
Handles relation cataloging, triple insertion, and evidence linking.
"""

import sqlite3
from typing import Optional


def ensure_relation(conn: sqlite3.Connection, rel_id: str, name: str, domain: str, range_: str) -> None:
    """
    Ensure a relation exists in the relations table (insert if missing).
    
    Args:
        conn: Database connection
        rel_id: Relation ID (e.g., "TREATS", "CAUSES")
        name: Human-readable relation name
        domain: Domain entity type
        range_: Range entity type
    """
    cursor = conn.execute(
        "SELECT rel_id FROM relations WHERE rel_id = ?",
        (rel_id,)
    )
    
    if not cursor.fetchone():
        conn.execute(
            """
            INSERT INTO relations (rel_id, name, domain_type, range_type)
            VALUES (?, ?, ?, ?)
            """,
            (rel_id, name, domain, range_)
        )
        conn.commit()


def insert_triple(
    conn: sqlite3.Connection,
    head_entity: int,
    rel_id: str,
    tail_entity: int,
    confidence: float,
    verifier_model: str,
    prompt_id: Optional[int] = None
) -> int:
    """
    Insert a verified triple into the triples table.
    
    Args:
        conn: Database connection
        head_entity: Head entity ID (references entities.entity_id)
        rel_id: Relation ID (references relations.rel_id)
        tail_entity: Tail entity ID (references entities.entity_id)
        confidence: Confidence score (0.0-1.0)
        verifier_model: Model name used for verification
        prompt_id: Optional prompt ID
        
    Returns:
        triple_id of inserted triple
    """
    cursor = conn.execute(
        """
        INSERT INTO triples (head_entity, rel_id, tail_entity, confidence, verifier_model, prompt_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (head_entity, rel_id, tail_entity, confidence, verifier_model, prompt_id)
    )
    conn.commit()
    return cursor.lastrowid


def insert_evidence(
    conn: sqlite3.Connection,
    triple_id: int,
    doc_id: int,
    section: str,
    sent_start: int,
    sent_end: int,
    sentence_text: str
) -> int:
    """
    Insert evidence linking a triple to its source sentence.
    
    Args:
        conn: Database connection
        triple_id: Triple ID (references triples.triple_id)
        doc_id: Document ID (references docs.doc_id)
        section: Section name (e.g., "RESULTS", "METHODS", "DISCUSSION")
        sent_start: Start sentence index (inclusive)
        sent_end: End sentence index (inclusive)
        sentence_text: Verbatim sentence text
        
    Returns:
        evidence_id of inserted evidence
    """
    cursor = conn.execute(
        """
        INSERT INTO evidence (triple_id, doc_id, section, sent_start, sent_end, sentence_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (triple_id, doc_id, section, sent_start, sent_end, sentence_text)
    )
    conn.commit()
    return cursor.lastrowid

