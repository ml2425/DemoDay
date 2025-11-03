"""
Test MCQ generation validation.
"""

import pytest
from pipeline.mcq_generator import generate_mcq, validate_mcq


def test_mcq_generator_refuses_without_evidence():
    """
    Ensure MCQ generator refuses when no evidence is provided.
    """
    triple = {
        "head_entity": {"canonical_name": "Test"},
        "rel_id": "TREATS",
        "tail_entity": {"canonical_name": "Disease"}
    }
    
    # Should raise ValueError when no evidence
    with pytest.raises(ValueError, match="Cannot generate MCQ without evidence"):
        generate_mcq(triple, [], {})


def test_mcq_includes_citation_when_present():
    """
    Ensure MCQ includes citation when evidence and document metadata are present.
    """
    triple = {
        "head_entity": {"canonical_name": "Test Drug"},
        "rel_id": "TREATS",
        "tail_entity": {"canonical_name": "Test Disease"}
    }
    
    evidence = [
        {
            "sentence_text": "Test drug effectively treats test disease.",
            "pmid": "12345678"
        }
    ]
    
    doc_metadata = {
        "pmid": "12345678"
    }
    
    mcq = generate_mcq(triple, evidence, doc_metadata)
    
    # Check that citation is included
    assert "citations_json" in mcq
    assert mcq["citations_json"] != "[]"
    assert "PMID:" in mcq["citations_json"] or "12345678" in mcq["citations_json"]


def test_mcq_includes_citation_with_doi():
    """Test MCQ citation with DOI instead of PMID."""
    triple = {
        "head_entity": {"canonical_name": "Test"},
        "rel_id": "CAUSES",
        "tail_entity": {"canonical_name": "Effect"}
    }
    
    evidence = [
        {
            "sentence_text": "Test causes effect.",
        }
    ]
    
    doc_metadata = {
        "doi": "10.1234/test.doi"
    }
    
    mcq = generate_mcq(triple, evidence, doc_metadata)
    
    assert "citations_json" in mcq
    assert "DOI:" in mcq["citations_json"] or "10.1234" in mcq["citations_json"]


def test_validate_mcq_requires_citation():
    """Test that MCQ validation requires citation."""
    mcq_no_citation = {
        "stem": "Test question?",
        "options_json": "[]",
        "explanation": "Test explanation",
        "citations_json": "[]"
    }
    
    assert validate_mcq(mcq_no_citation, []) is False
    
    mcq_with_citation = {
        "stem": "Test question?",
        "options_json": "[]",
        "explanation": "Test explanation",
        "citations_json": '["PMID:12345678"]'
    }
    
    assert validate_mcq(mcq_with_citation, []) is True

