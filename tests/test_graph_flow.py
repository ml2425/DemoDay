"""
End-to-end test for orchestrator pipeline flow.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from database.db_utils import connect, insert_doc
from database.triple_utils import ensure_relation
from pipeline.graph import build_graph, Orchestrator


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
    
    # Ensure TREATS relation exists
    ensure_relation(conn, "TREATS", "treats", "DRUG", "DISORDER")
    
    yield conn
    
    conn.close()
    Path(db_path).unlink()


def test_graph_end_to_end(test_db):
    """Test end-to-end pipeline: document → triples → MCQs."""
    conn = test_db
    
    # Insert a test document
    doc_id = insert_doc(conn, source_kind="LOCAL_PDF", sha256="test_graph_flow_sha")
    
    # Text containing medical entities
    text = "Metformin is first-line therapy for type 2 diabetes."
    
    # Run orchestrator
    orchestrator = Orchestrator(conn)
    result = orchestrator.run_doc(doc_id, text)
    
    # Assertions
    assert result["sentences_processed"] >= 0
    assert result["triples_created"] >= 1, "Should create at least one triple"
    assert result["mcqs_created"] >= 1, "Should create at least one MCQ"
    
    # Verify triple was created
    cursor = conn.execute("SELECT COUNT(*) FROM triples")
    triple_count = cursor.fetchone()[0]
    assert triple_count >= 1
    
    # Verify evidence was created
    cursor = conn.execute("SELECT COUNT(*) FROM evidence")
    evidence_count = cursor.fetchone()[0]
    assert evidence_count >= 1
    
    # Verify MCQ was created
    cursor = conn.execute("SELECT COUNT(*) FROM mcqs")
    mcq_count = cursor.fetchone()[0]
    assert mcq_count >= 1


def test_build_graph():
    """Test build_graph function."""
    # Create a temp file path for the test
    import tempfile
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()
    
    # Copy schema to test file
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    if schema_path.exists():
        conn2 = sqlite3.connect(db_path)
        conn2.execute("PRAGMA foreign_keys = ON")
        with open(schema_path, 'r') as f:
            conn2.executescript(f.read())
        conn2.close()
    
    orchestrator = build_graph(db_path=db_path)
    
    assert isinstance(orchestrator, Orchestrator)
    assert orchestrator.conn is not None
    
    # Close connection before cleanup
    orchestrator.conn.close()
    
    # Cleanup
    Path(db_path).unlink()

