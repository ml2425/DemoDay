"""
End-to-end test for MCQ generation.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from database.db_utils import connect, insert_doc
from database.entity_utils import upsert_concept, insert_entity
from database.triple_utils import ensure_relation, insert_triple, insert_evidence
from pipeline.mcq_generator import MCQGeneratorNode


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


def test_mcq_generation_end2end(test_db):
    """Test end-to-end MCQ generation from triple with evidence."""
    conn = test_db
    
    # Insert document with PMID
    doc_id = insert_doc(conn, source_kind="PUBMED_ABSTRACT", sha256="test_mcq_sha", pmid="12345678")
    
    # Insert two concepts (DRUG and DISORDER)
    drug_concept_id = upsert_concept(conn, "Metformin", "DRUG", 0.9)
    disorder_concept_id = upsert_concept(conn, "Type 2 Diabetes", "DISORDER", 0.9)
    
    # Insert two entities
    drug_entity_id = insert_entity(conn, drug_concept_id, doc_id, 0, 0, 8, "Metformin")
    disorder_entity_id = insert_entity(conn, disorder_concept_id, doc_id, 0, 20, 35, "Type 2 Diabetes")
    
    # Ensure TREATS relation
    ensure_relation(conn, "TREATS", "treats", "DRUG", "DISORDER")
    
    # Insert triple
    triple_id = insert_triple(
        conn,
        head_entity=drug_entity_id,
        rel_id="TREATS",
        tail_entity=disorder_entity_id,
        confidence=0.85,
        verifier_model="heuristic"
    )
    
    # Insert one-sentence evidence
    insert_evidence(
        conn,
        triple_id=triple_id,
        doc_id=doc_id,
        section="RESULTS",
        sent_start=0,
        sent_end=0,
        sentence_text="Metformin is used to treat type 2 diabetes."
    )
    
    # Generate MCQ
    generator = MCQGeneratorNode(conn)
    mcq = generator.generate_for_triple(triple_id)
    
    # Assertions
    assert "options" in mcq or "options_json" in mcq
    
    # Parse options
    if "options" in mcq:
        options = mcq["options"]
    else:
        import json
        options = json.loads(mcq["options_json"])
    
    # Assert 5 options
    assert len(options) == 5, f"Expected 5 options, got {len(options)}"
    
    # Assert exactly one correct
    correct_count = sum(1 for opt in options if opt.get("correct", False))
    assert correct_count == 1, f"Expected 1 correct option, got {correct_count}"
    
    # Assert explanation contains PMID
    assert "PMID:" in mcq["explanation"], "Explanation must contain PMID citation"
    
    # Assert one new row in mcqs
    cursor = conn.execute("SELECT COUNT(*) FROM mcqs WHERE triple_id = ?", (triple_id,))
    assert cursor.fetchone()[0] == 1, "Expected exactly one MCQ row"
    
    # Assert mcq_id matches
    cursor = conn.execute("SELECT mcq_id FROM mcqs WHERE triple_id = ?", (triple_id,))
    db_mcq_id = cursor.fetchone()[0]
    assert mcq["mcq_id"] == db_mcq_id

