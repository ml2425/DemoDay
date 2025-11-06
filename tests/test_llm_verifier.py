"""
Test LLM-based relation verification.
"""

import os
import pytest
import sqlite3
from pathlib import Path
from pipeline.verifier import RelationVerifierNode
from database.db_utils import connect


@pytest.fixture
def test_db():
    """Create test database with schema."""
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


@pytest.fixture
def verifier(test_db):
    """Create verifier with test database."""
    return RelationVerifierNode(test_db)


def test_verify_abbreviation_match(verifier):
    """Test LLM handles abbreviation MRI → Magnetic Resonance Imaging"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API key")
    
    sentence = "MRI showed enhancing mass in right frontal lobe."
    triple = ("Magnetic Resonance Imaging", "INVESTIGATED_BY", "Brain Neoplasm")
    
    result = verifier.verify(sentence, triple)
    
    assert result["entailed"] == True, "Should recognize MRI = Magnetic Resonance Imaging"
    assert result["confidence"] > 0.7
    assert "reasoning" in result


def test_verify_synonym_match(verifier):
    """Test LLM handles synonym TMZ → Temozolomide"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API key")
    
    sentence = "Patient treated with TMZ and radiation therapy."
    triple = ("Temozolomide", "TREATS", "Glioblastoma")
    
    result = verifier.verify(sentence, triple)
    
    assert result["entailed"] == True, "Should recognize TMZ = Temozolomide"
    assert result["confidence"] > 0.7
    assert "reasoning" in result


def test_verify_wrong_relationship(verifier):
    """Test LLM rejects incorrect relationship"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API key")
    
    sentence = "MRI was performed to assess tumor extent."
    triple = ("Magnetic Resonance Imaging", "TREATS", "Glioma")
    
    result = verifier.verify(sentence, triple)
    
    assert result["entailed"] == False, "MRI doesn't treat, it investigates"


def test_verify_negation(verifier):
    """Test LLM rejects negated statements"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API key")
    
    sentence = "No evidence of tumor recurrence on follow-up MRI."
    triple = ("Brain", "HAS_FINDING", "Neoplasm")
    
    result = verifier.verify(sentence, triple)
    
    assert result["entailed"] == False, "Should reject negated relationship"


def test_verify_caching(verifier):
    """Test that identical verifications use cache"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API key")
    
    sentence = "Patient has headache."
    triple = ("Patient", "HAS_FINDING", "Headache")
    
    # First call - hits LLM
    result1 = verifier.verify(sentence, triple)
    
    # Second call - should hit cache
    result2 = verifier.verify(sentence, triple)
    
    assert result1 == result2, "Cached result should match original"
    assert result1["entailed"] == result2["entailed"]
    assert result1["confidence"] == result2["confidence"]

