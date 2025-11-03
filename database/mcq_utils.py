"""
MCQ database utilities.
Handles evidence retrieval, concept lookups, distractor sampling, and MCQ insertion.
"""

import json
import sqlite3
import random
from typing import List, Dict, Set, Optional


def get_evidence_for_triple(conn: sqlite3.Connection, triple_id: int) -> List[Dict]:
    """
    Get evidence rows for a triple, joined with document metadata.
    
    Args:
        conn: Database connection
        triple_id: Triple ID
        
    Returns:
        List of dicts with keys: {doc_id, pmid, doi, sentence_text}
        Ordered by evidence_id
    """
    cursor = conn.execute(
        """
        SELECT e.doc_id, d.pmid, d.doi, e.sentence_text
        FROM evidence e
        JOIN docs d ON e.doc_id = d.doc_id
        WHERE e.triple_id = ?
        ORDER BY e.evidence_id
        """,
        (triple_id,)
    )
    
    rows = cursor.fetchall()
    return [
        {
            "doc_id": row[0],
            "pmid": row[1],
            "doi": row[2],
            "sentence_text": row[3]
        }
        for row in rows
    ]


def get_concept_for_entity(conn: sqlite3.Connection, entity_id: int) -> Dict:
    """
    Get concept information for an entity.
    
    Args:
        conn: Database connection
        entity_id: Entity ID
        
    Returns:
        Dict with keys: {canonical_id, canonical_name, semantic_category}
    """
    cursor = conn.execute(
        """
        SELECT c.canonical_id, c.canonical_name, c.semantic_category
        FROM concepts c
        JOIN entities e ON c.canonical_id = e.canonical_id
        WHERE e.entity_id = ?
        """,
        (entity_id,)
    )
    
    row = cursor.fetchone()
    if row:
        return {
            "canonical_id": row[0],
            "canonical_name": row[1],
            "semantic_category": row[2]
        }
    return {}


def sample_distractors(
    conn: sqlite3.Connection,
    semantic_category: str,
    exclude_names: Set[str],
    k: int = 4
) -> List[str]:
    """
    Sample up to k canonical names from concepts with same category, excluding exclude_names.
    
    Args:
        conn: Database connection
        semantic_category: Category to sample from
        exclude_names: Set of names to exclude
        k: Number of distractors to sample
        
    Returns:
        List of canonical names (any order)
    """
    if exclude_names:
        placeholders = ','.join('?' * len(exclude_names))
        query = f"""
            SELECT canonical_name
            FROM concepts
            WHERE semantic_category = ? AND canonical_name NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """
        params = (semantic_category,) + tuple(exclude_names) + (k,)
    else:
        query = """
            SELECT canonical_name
            FROM concepts
            WHERE semantic_category = ?
            ORDER BY RANDOM()
            LIMIT ?
        """
        params = (semantic_category, k)
    
    cursor = conn.execute(query, params)
    
    names = [row[0] for row in cursor.fetchall()]
    
    # Fill with generic placeholders if needed
    while len(names) < k:
        names.append(f"Option {len(names) + 1}")
    
    return names[:k]


def insert_mcq(
    conn: sqlite3.Connection,
    triple_id: int,
    stem: str,
    options: List[Dict],
    explanation: str,
    citations: List[Dict],
    topic: str = "",
    difficulty: str = "medium",
    status: str = "pending"
) -> int:
    """
    Insert an MCQ into the mcqs table.
    
    Args:
        conn: Database connection
        triple_id: Triple ID
        stem: Question stem
        options: List of option dicts (must have 'text' and 'correct' keys)
        explanation: Explanation text
        citations: List of citation dicts
        topic: Topic string
        difficulty: Difficulty level
        status: Status (default: "pending")
        
    Returns:
        mcq_id of inserted MCQ
    """
    # Serialize to JSON
    options_json = json.dumps(options)
    citations_json = json.dumps(citations)
    
    cursor = conn.execute(
        """
        INSERT INTO mcqs (triple_id, stem, options_json, explanation, citations_json, topic, difficulty, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (triple_id, stem, options_json, explanation, citations_json, topic, difficulty, status)
    )
    conn.commit()
    return cursor.lastrowid


def list_mcqs(conn: sqlite3.Connection, status: str = "pending", limit: int = 20) -> List[Dict]:
    """
    List MCQs by status.
    
    Args:
        conn: Database connection
        status: Status filter (default: "pending")
        limit: Maximum number of MCQs to return
        
    Returns:
        List of MCQ dictionaries with all fields
    """
    cursor = conn.execute(
        """
        SELECT mcq_id, triple_id, stem, options_json, explanation, citations_json,
               topic, difficulty, status, human_feedback
        FROM mcqs
        WHERE status = ?
        ORDER BY mcq_id
        LIMIT ?
        """,
        (status, limit)
    )
    
    rows = cursor.fetchall()
    mcqs = []
    for row in rows:
        mcq = {
            "mcq_id": row[0],
            "triple_id": row[1],
            "stem": row[2],
            "options_json": row[3],
            "explanation": row[4],
            "citations_json": row[5],
            "topic": row[6],
            "difficulty": row[7],
            "status": row[8],
            "human_feedback": row[9]
        }
        # Parse JSON fields
        if mcq["options_json"]:
            mcq["options"] = json.loads(mcq["options_json"])
        else:
            mcq["options"] = []
        
        if mcq["citations_json"]:
            mcq["citations"] = json.loads(mcq["citations_json"])
        else:
            mcq["citations"] = []
        
        mcqs.append(mcq)
    
    return mcqs


def get_mcq(conn: sqlite3.Connection, mcq_id: int) -> Optional[Dict]:
    """
    Get a single MCQ by ID.
    
    Args:
        conn: Database connection
        mcq_id: MCQ ID
        
    Returns:
        MCQ dictionary or None if not found
    """
    cursor = conn.execute(
        """
        SELECT mcq_id, triple_id, stem, options_json, explanation, citations_json,
               topic, difficulty, status, human_feedback
        FROM mcqs
        WHERE mcq_id = ?
        """,
        (mcq_id,)
    )
    
    row = cursor.fetchone()
    if not row:
        return None
    
    mcq = {
        "mcq_id": row[0],
        "triple_id": row[1],
        "stem": row[2],
        "options_json": row[3],
        "explanation": row[4],
        "citations_json": row[5],
        "topic": row[6],
        "difficulty": row[7],
        "status": row[8],
        "human_feedback": row[9]
    }
    
    # Parse JSON fields
    if mcq["options_json"]:
        mcq["options"] = json.loads(mcq["options_json"])
    else:
        mcq["options"] = []
    
    if mcq["citations_json"]:
        mcq["citations"] = json.loads(mcq["citations_json"])
    else:
        mcq["citations"] = []
    
    return mcq


def update_mcq_status(
    conn: sqlite3.Connection,
    mcq_id: int,
    status: str,
    feedback: str = ""
) -> None:
    """
    Update MCQ status and optionally feedback.
    
    Args:
        conn: Database connection
        mcq_id: MCQ ID
        status: New status (e.g., "approved", "rejected")
        feedback: Optional feedback text
    """
    conn.execute(
        """
        UPDATE mcqs
        SET status = ?, human_feedback = ?
        WHERE mcq_id = ?
        """,
        (status, feedback, mcq_id)
    )
    conn.commit()

