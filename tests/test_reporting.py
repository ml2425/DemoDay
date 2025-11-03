"""
Test reporting and summary functions.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from scripts.report_summary import (
    open_conn,
    overall_counts,
    provenance_metrics,
    mcq_status_breakdown,
    per_doc_summary,
    render_table
)
from database.db_utils import insert_doc
from database.entity_utils import upsert_concept, insert_entity
from database.triple_utils import ensure_relation, insert_triple, insert_evidence
from database.mcq_utils import insert_mcq


@pytest.fixture
def test_db():
    """Create test database with schema and seed data."""
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
    
    # Seed minimal data
    # 1 doc
    doc_id = insert_doc(conn, source_kind="LOCAL_PDF", sha256="test_report_sha", pmid="12345678")
    
    # 2 concepts
    concept1_id = upsert_concept(conn, "Aspirin", "DRUG", 1.0)
    concept2_id = upsert_concept(conn, "Migraine", "DISORDER", 1.0)
    
    # 2 entities
    entity1_id = insert_entity(conn, concept1_id, doc_id, 0, 0, 6, "Aspirin")
    entity2_id = insert_entity(conn, concept2_id, doc_id, 0, 10, 18, "Migraine")
    
    # 1 relation
    ensure_relation(conn, "TREATS", "treats", "DRUG", "DISORDER")
    
    # 1 triple
    triple_id = insert_triple(conn, entity1_id, "TREATS", entity2_id, 0.8, "heuristic")
    
    # 1 evidence
    insert_evidence(conn, triple_id, doc_id, "RESULTS", 0, 0, "Aspirin treats migraine.")
    
    # 1 MCQ
    options = [{"text": "Aspirin", "correct": True}, {"text": "Placebo", "correct": False}]
    citations = [{"pmid": "12345678"}]
    insert_mcq(conn, triple_id, "Which drug treats migraine?", options, "Aspirin treats migraine.", citations, status="pending")
    
    conn.commit()
    
    yield conn, db_path
    
    conn.close()
    Path(db_path).unlink()


def test_overall_counts(test_db):
    """Test overall_counts function."""
    conn, _ = test_db
    
    counts = overall_counts(conn)
    
    # Check structure
    assert "docs" in counts
    assert "concepts" in counts
    assert "entities" in counts
    assert "relations" in counts
    assert "triples" in counts
    assert "evidence" in counts
    assert "mcqs" in counts
    
    # Check types
    assert all(isinstance(v, int) for v in counts.values())
    
    # Check that we have at least the seeded data
    assert counts["docs"] >= 1
    assert counts["concepts"] >= 2
    assert counts["entities"] >= 2
    assert counts["triples"] >= 1
    assert counts["evidence"] >= 1
    assert counts["mcqs"] >= 1


def test_provenance_metrics(test_db):
    """Test provenance_metrics function."""
    conn, _ = test_db
    
    metrics = provenance_metrics(conn)
    
    # Check structure
    assert "triples_with_evidence" in metrics
    assert "triples_total" in metrics
    assert "provenance_completeness" in metrics
    assert "avg_triple_confidence" in metrics
    
    # Check types
    assert isinstance(metrics["triples_with_evidence"], int)
    assert isinstance(metrics["triples_total"], int)
    assert isinstance(metrics["provenance_completeness"], float)
    assert metrics["avg_triple_confidence"] is None or isinstance(metrics["avg_triple_confidence"], float)
    
    # Check values
    assert 0.0 <= metrics["provenance_completeness"] <= 1.0
    assert metrics["triples_with_evidence"] <= metrics["triples_total"]
    
    # Check that we have at least the seeded triple with evidence
    assert metrics["triples_total"] >= 1
    assert metrics["triples_with_evidence"] >= 1


def test_mcq_status_breakdown(test_db):
    """Test mcq_status_breakdown function."""
    conn, _ = test_db
    
    breakdown = mcq_status_breakdown(conn)
    
    # Check structure
    assert isinstance(breakdown, dict)
    
    # Check that pending is present (we seeded one pending MCQ)
    assert "pending" in breakdown
    assert breakdown["pending"] >= 1


def test_per_doc_summary(test_db):
    """Test per_doc_summary function."""
    conn, _ = test_db
    
    summaries = per_doc_summary(conn)
    
    # Check structure
    assert isinstance(summaries, list)
    assert len(summaries) >= 1
    
    # Check first summary structure
    summary = summaries[0]
    assert "doc_id" in summary
    assert "source_kind" in summary
    assert "pmid" in summary
    assert "doi" in summary
    assert "entities" in summary
    assert "triples" in summary
    assert "evidence_rows" in summary
    assert "mcqs" in summary
    assert "triples_with_evidence" in summary
    
    # Check types
    assert isinstance(summary["doc_id"], int)
    assert isinstance(summary["entities"], int)
    assert isinstance(summary["triples"], int)
    assert isinstance(summary["evidence_rows"], int)
    assert isinstance(summary["mcqs"], int)
    assert isinstance(summary["triples_with_evidence"], int)


def test_render_table():
    """Test render_table function."""
    rows = [
        {"name": "Alice", "age": 30, "city": "NYC"},
        {"name": "Bob", "age": 25, "city": "LA"}
    ]
    cols = ["name", "age", "city"]
    
    table = render_table(rows, cols)
    
    assert isinstance(table, str)
    assert "Alice" in table
    assert "Bob" in table
    assert "30" in table
    assert "25" in table


def test_open_conn(test_db):
    """Test open_conn function."""
    _, db_path = test_db
    
    conn = open_conn(db_path)
    assert conn is not None
    
    # Test that it's a valid connection
    cursor = conn.execute("SELECT 1")
    assert cursor.fetchone()[0] == 1
    
    conn.close()


def test_empty_db_handling():
    """Test that functions handle empty database gracefully."""
    # Create empty database
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Load schema only
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
    
    try:
        # Test that all functions return valid defaults
        counts = overall_counts(conn)
        assert all(v == 0 for v in counts.values())
        
        metrics = provenance_metrics(conn)
        assert metrics["triples_total"] == 0
        assert metrics["triples_with_evidence"] == 0
        assert metrics["provenance_completeness"] == 0.0
        
        breakdown = mcq_status_breakdown(conn)
        assert breakdown["pending"] == 0
        
        summaries = per_doc_summary(conn)
        assert summaries == []
    
    finally:
        conn.close()
        Path(db_path).unlink()

