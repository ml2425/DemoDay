"""
Test review helper functions (non-UI).
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from database.db_utils import connect, insert_doc
from database.mcq_utils import insert_mcq, list_mcqs, update_mcq_status, get_mcq


@pytest.fixture
def test_db():
    """Create test database with schema."""
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Load schema
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
    
    yield conn
    
    conn.close()
    Path(db_path).unlink()


def test_update_mcq_status(test_db):
    """Test updating MCQ status and feedback."""
    conn = test_db
    
    # Insert a test document and triple (minimal setup)
    doc_id = insert_doc(conn, source_kind="LOCAL_PDF", sha256="test_review_sha")
    
    # Insert a minimal triple for the MCQ
    cursor = conn.execute(
        "INSERT INTO concepts (canonical_name, semantic_category) VALUES (?, ?)",
        ("test_concept", "DISORDER")
    )
    concept_id = cursor.lastrowid
    
    cursor = conn.execute(
        "INSERT INTO entities (canonical_id, doc_id, sent_idx, span_text) VALUES (?, ?, ?, ?)",
        (concept_id, doc_id, 0, "test")
    )
    entity_id = cursor.lastrowid
    
    conn.execute(
        "INSERT INTO relations (rel_id, name, domain_type, range_type) VALUES (?, ?, ?, ?)",
        ("TEST", "test", "DISORDER", "DISORDER")
    )
    
    cursor = conn.execute(
        "INSERT INTO triples (head_entity, rel_id, tail_entity, confidence, verifier_model) VALUES (?, ?, ?, ?, ?)",
        (entity_id, "TEST", entity_id, 0.5, "test")
    )
    triple_id = cursor.lastrowid
    conn.commit()
    
    # Insert MCQ with status pending
    mcq_id = insert_mcq(
        conn,
        triple_id=triple_id,
        stem="Test question?",
        options=[{"text": "Answer", "correct": True}, {"text": "Wrong", "correct": False}],
        explanation="Test explanation",
        citations=[{"type": "pmid", "value": "123"}],
        status="pending"
    )
    
    # Verify initial status
    mcq = get_mcq(conn, mcq_id)
    assert mcq is not None
    assert mcq["status"] == "pending"
    assert mcq["human_feedback"] is None or mcq["human_feedback"] == ""
    
    # Update status to approved with feedback
    update_mcq_status(conn, mcq_id, "approved", "ok")
    
    # Verify update
    updated_mcq = get_mcq(conn, mcq_id)
    assert updated_mcq["status"] == "approved"
    assert updated_mcq["human_feedback"] == "ok"
    
    # Verify it's no longer in pending list
    pending = list_mcqs(conn, status="pending")
    pending_ids = [m["mcq_id"] for m in pending]
    assert mcq_id not in pending_ids
    
    # Verify it's in approved list
    approved = list_mcqs(conn, status="approved")
    approved_ids = [m["mcq_id"] for m in approved]
    assert mcq_id in approved_ids

