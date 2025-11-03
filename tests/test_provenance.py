"""
Test provenance logging and evidence window utilities.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from database.db_utils import connect, insert_doc
from database.provenance_utils import prompt_sha, upsert_prompt
from database.triple_utils import ensure_relation, insert_triple, insert_evidence
from utils.text_window import build_window


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


def test_prompt_upsert_by_hash(test_db):
    """Test that same prompt content returns same prompt_id."""
    conn = test_db
    
    content = "Verify if this relation is entailed by the evidence."
    role = "user"
    
    # First insert
    prompt_id_1 = upsert_prompt(conn, role, content)
    
    # Second insert with same content
    prompt_id_2 = upsert_prompt(conn, role, content)
    
    # Should return same prompt_id
    assert prompt_id_1 == prompt_id_2
    
    # Verify only one row exists
    cursor = conn.execute("SELECT COUNT(*) FROM prompts WHERE sha256 = ?", (prompt_sha(content),))
    assert cursor.fetchone()[0] == 1


def test_build_window(test_db):
    """Test evidence window building with 3 sentences."""
    sentences = [
        "Patient presented with headache.",
        "CT scan revealed no abnormalities.",
        "Follow-up MRI confirmed normal findings.",
        "Treatment was not required.",
        "Patient was discharged."
    ]
    
    # Build window around center sentence (index 1)
    start_idx, end_idx, joined_text = build_window(sentences, center_idx=1, max_sentences=3)
    
    # Assert indices are valid
    assert start_idx >= 0
    assert end_idx < len(sentences)
    assert start_idx <= end_idx
    
    # Assert constraint: end_idx - start_idx < 3 (inclusive range)
    # If start=0, end=2, then diff = 2, which is < 3 ✓
    assert (end_idx - start_idx) < 3
    
    # Assert joined text contains expected sentences
    assert "CT scan" in joined_text
    
    # Test edge case: center at beginning
    start_idx, end_idx, joined_text = build_window(sentences, center_idx=0, max_sentences=3)
    assert start_idx == 0
    assert (end_idx - start_idx) < 3
    
    # Test edge case: center at end
    start_idx, end_idx, joined_text = build_window(sentences, center_idx=4, max_sentences=3)
    assert end_idx == 4
    assert (end_idx - start_idx) < 3


def test_triple_with_prompt_and_evidence(test_db):
    """Test inserting triple with prompt_id and evidence from window."""
    conn = test_db
    
    # Insert document
    doc_id = insert_doc(conn, source_kind="LOCAL_PDF", sha256="test_provenance_sha")
    
    # Insert entities first (for foreign key constraints)
    # Using concept and entity utils would require full setup, so we'll create minimal entities
    cursor = conn.execute(
        "INSERT INTO concepts (canonical_name, semantic_category) VALUES (?, ?)",
        ("test_drug", "DRUG")
    )
    concept_id = cursor.lastrowid
    
    cursor = conn.execute(
        "INSERT INTO entities (canonical_id, doc_id, sent_idx, span_text) VALUES (?, ?, ?, ?)",
        (concept_id, doc_id, 0, "test_drug")
    )
    entity_id = cursor.lastrowid
    
    # Ensure relation
    ensure_relation(conn, "TREATS", "treats", "DRUG", "DISORDER")
    
    # Log prompt
    prompt_content = "Verify if drug treats disorder."
    prompt_id = upsert_prompt(conn, "user", prompt_content)
    
    # Insert triple with prompt_id
    triple_id = insert_triple(
        conn,
        head_entity=entity_id,
        rel_id="TREATS",
        tail_entity=entity_id,  # Using same entity for simplicity
        confidence=0.75,
        verifier_model="heuristic",
        prompt_id=prompt_id
    )
    
    # Build evidence window
    sentences = [
        "Patient received treatment.",
        "Drug was administered successfully.",
        "Symptoms improved."
    ]
    start_idx, end_idx, window_text = build_window(sentences, center_idx=1, max_sentences=3)
    
    # Insert evidence
    evidence_id = insert_evidence(
        conn,
        triple_id=triple_id,
        doc_id=doc_id,
        section="RESULTS",
        sent_start=start_idx,
        sent_end=end_idx,
        sentence_text=window_text
    )
    
    # Assert counts
    cursor = conn.execute("SELECT COUNT(*) FROM triples WHERE triple_id = ?", (triple_id,))
    assert cursor.fetchone()[0] == 1
    
    cursor = conn.execute("SELECT COUNT(*) FROM evidence WHERE evidence_id = ?", (evidence_id,))
    assert cursor.fetchone()[0] == 1
    
    # Assert evidence links to triple
    cursor = conn.execute(
        "SELECT triple_id FROM evidence WHERE evidence_id = ?",
        (evidence_id,)
    )
    assert cursor.fetchone()[0] == triple_id
    
    # Assert triple has prompt_id
    cursor = conn.execute(
        "SELECT prompt_id FROM triples WHERE triple_id = ?",
        (triple_id,)
    )
    assert cursor.fetchone()[0] == prompt_id

