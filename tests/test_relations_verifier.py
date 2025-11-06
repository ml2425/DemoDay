"""
Test relation extraction and verification.
"""

import pytest
from database.db_utils import connect, insert_doc
from database.triple_utils import ensure_relation, insert_triple, insert_evidence
from pipeline.relations import RelationExtractor
from pipeline.verifier import RelationVerifierNode


@pytest.fixture
def test_db():
    """Create test database with schema."""
    import sqlite3
    from pathlib import Path
    import tempfile
    
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


def test_relation_extraction_and_verification(test_db):
    """Test relation extraction, verification, and database writes."""
    conn = test_db
    
    # Insert a test document
    doc_id = insert_doc(conn, source_kind="LOCAL_PDF", sha256="test_sha256")
    
    # Ensure TREATS relation exists
    ensure_relation(conn, "TREATS", "treats", "DRUG", "DISORDER")
    
    # Create entities dict format (as if from Phase 6)
    entities = [
        {"entity_id": 1, "name": "vancomycin", "type": "DRUG", "span_text": "vancomycin"},
        {"entity_id": 2, "name": "bacterial meningitis", "type": "DISORDER", "span_text": "bacterial meningitis"}
    ]
    
    # Test relation extraction
    sentence = "Vancomycin is used to treat bacterial meningitis."
    extractor = RelationExtractor(conn=conn)  # Pass conn for caching
    candidates = extractor.candidates(sentence, entities)
    
    assert len(candidates) > 0, "Should extract at least one candidate"
    # Check for Dict format with correct relation
    found = False
    for candidate in candidates:
        if (candidate.get("head", "").lower() == "vancomycin" and 
            candidate.get("relation") == "TREATS" and 
            candidate.get("tail", "").lower() == "bacterial meningitis"):
            found = True
            # Verify Dict has required keys
            assert "confidence" in candidate
            assert "evidence" in candidate
            break
    assert found, "Should find TREATS relation between vancomycin and bacterial meningitis"
    
    # Test verification
    verifier = RelationVerifierNode(conn)
    triple = ("vancomycin", "TREATS", "bacterial meningitis")
    result = verifier.verify(sentence, triple)
    
    assert "entailed" in result
    assert "confidence" in result
    
    # If entailed, write to database
    if result["entailed"]:
        # Insert triple (using entity_ids from entities list)
        triple_id = insert_triple(
            conn,
            head_entity=1,
            rel_id="TREATS",
            tail_entity=2,
            confidence=result["confidence"],
            verifier_model=verifier.verifier_model
        )
        
        # Insert evidence
        insert_evidence(
            conn,
            triple_id=triple_id,
            doc_id=doc_id,
            section="RESULTS",
            sent_start=0,
            sent_end=0,
            sentence_text=sentence
        )
        
        # Assert triple count
        cursor = conn.execute("SELECT COUNT(*) FROM triples WHERE triple_id = ?", (triple_id,))
        assert cursor.fetchone()[0] == 1
        
        # Assert evidence links to triple
        cursor = conn.execute("SELECT COUNT(*) FROM evidence WHERE triple_id = ?", (triple_id,))
        assert cursor.fetchone()[0] == 1
        
        # Assert evidence references triple
        cursor = conn.execute(
            """
            SELECT e.evidence_id FROM evidence e
            JOIN triples t ON e.triple_id = t.triple_id
            WHERE t.triple_id = ?
            """,
            (triple_id,)
        )
        assert cursor.fetchone() is not None

