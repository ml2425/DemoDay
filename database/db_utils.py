"""Database utilities for SQLite operations."""

import sqlite3
from pathlib import Path
from typing import Optional
import json

ROOT = Path(__file__).parent.parent


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Connect to SQLite database.
    
    Args:
        db_path: Path to database file. Defaults to database/kg.sqlite
        
    Returns:
        SQLite connection object
    """
    if db_path is None:
        db_path = ROOT / "database" / "kg.sqlite"
    
    # Ensure database directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize database schema from schema.sql.
    
    Args:
        db_path: Path to database file. Defaults to database/kg.sqlite
    """
    conn = connect(db_path)
    
    schema_file = Path(__file__).parent / "schema.sql"
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print(f"[OK] Database initialized at {db_path or 'database/kg.sqlite'}")


def get_source(conn: sqlite3.Connection, source_id: str) -> Optional[dict]:
    """Get source by source_id."""
    cursor = conn.execute(
        "SELECT * FROM sources WHERE source_id = ?",
        (source_id,)
    )
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def insert_source(
    conn: sqlite3.Connection,
    source_id: str,
    source_type: str,
    full_text: str,
    metadata_json: Optional[dict] = None
) -> None:
    """Insert a new source."""
    metadata_str = json.dumps(metadata_json) if metadata_json else None
    conn.execute(
        """INSERT OR REPLACE INTO sources 
           (source_id, source_type, full_text, metadata_json)
           VALUES (?, ?, ?, ?)""",
        (source_id, source_type, full_text, metadata_str)
    )
    conn.commit()


def insert_triple(
    conn: sqlite3.Connection,
    source_id: str,
    head_entity: str,
    relation: str,
    tail_entity: str,
    evidence_snippet: str,
    relation_raw: Optional[str] = None,
    location_paragraph: Optional[int] = None,
    location_sentence_start: Optional[int] = None,
    location_sentence_end: Optional[int] = None,
    location_char_start: Optional[int] = None,
    location_char_end: Optional[int] = None,
    confidence: float = 0.75
) -> int:
    """
    Insert a triple. Returns triple_id.
    """
    cursor = conn.execute(
        """INSERT OR IGNORE INTO triples 
           (source_id, head_entity, relation, relation_raw, tail_entity,
            evidence_snippet, location_paragraph, location_sentence_start,
            location_sentence_end, location_char_start, location_char_end,
            confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source_id, head_entity, relation, relation_raw, tail_entity,
         evidence_snippet, location_paragraph, location_sentence_start,
         location_sentence_end, location_char_start, location_char_end,
         confidence)
    )
    conn.commit()
    
    # Get the triple_id (either newly inserted or existing)
    cursor = conn.execute(
        """SELECT triple_id FROM triples 
           WHERE source_id = ? AND head_entity = ? AND relation = ? AND tail_entity = ?""",
        (source_id, head_entity, relation, tail_entity)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def insert_mcq(
    conn: sqlite3.Connection,
    triple_id: int,
    stem_scenario: str,
    question: str,
    choices: list[str],
    correct_index: int,
    explanation: str,
    triple_used: dict,
    verification_status: Optional[str] = None,
    verification_confidence: Optional[float] = None
) -> int:
    """
    Insert an MCQ. Returns mcq_id.
    """
    choices_json = json.dumps(choices)
    triple_used_json = json.dumps(triple_used)
    
    cursor = conn.execute(
        """INSERT INTO mcqs 
           (triple_id, stem_scenario, question, choices_json, correct_index,
            explanation, triple_used_json, verification_status, verification_confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (triple_id, stem_scenario, question, choices_json, correct_index,
         explanation, triple_used_json, verification_status, verification_confidence)
    )
    conn.commit()
    return cursor.lastrowid


def get_triple(conn: sqlite3.Connection, triple_id: int) -> Optional[dict]:
    """Get triple by triple_id."""
    cursor = conn.execute(
        "SELECT * FROM triples WHERE triple_id = ?",
        (triple_id,)
    )
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def get_mcqs_by_status(conn: sqlite3.Connection, status: str = "pending") -> list[dict]:
    """Get MCQs by status."""
    cursor = conn.execute(
        """SELECT m.*, t.head_entity, t.relation, t.tail_entity, t.evidence_snippet,
                  s.source_id, s.source_type, s.metadata_json
           FROM mcqs m
           JOIN triples t ON m.triple_id = t.triple_id
           JOIN sources s ON t.source_id = s.source_id
           WHERE m.status = ?
           ORDER BY m.created_at DESC""",
        (status,)
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def update_mcq_status(
    conn: sqlite3.Connection,
    mcq_id: int,
    status: str,
    feedback: Optional[str] = None
) -> None:
    """Update MCQ status and optionally add feedback."""
    conn.execute(
        """UPDATE mcqs 
           SET status = ?, user_feedback = ?, updated_at = CURRENT_TIMESTAMP
           WHERE mcq_id = ?""",
        (status, feedback, mcq_id)
    )
    conn.commit()
    
    # Log decision
    conn.execute(
        "INSERT INTO decisions (mcq_id, action, feedback) VALUES (?, ?, ?)",
        (mcq_id, status, feedback)
    )
    conn.commit()

