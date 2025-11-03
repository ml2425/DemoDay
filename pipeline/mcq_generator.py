"""
MCQ generation module.
Generates multiple-choice questions from verified triples with citations.
"""

from typing import Dict, Any, List, Optional


def generate_mcq(
    triple: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    doc_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a multiple-choice question from a verified triple.
    
    Args:
        triple: Triple dictionary with head_entity, rel_id, tail_entity
        evidence: List of evidence dictionaries with sentence_text and citations
        doc_metadata: Document metadata with pmid/doi
        
    Returns:
        Dictionary with 'stem', 'options_json', 'explanation', 'citations_json'
        
    Raises:
        ValueError: If no evidence is provided (zero hallucinations policy)
    """
    if not evidence or len(evidence) == 0:
        raise ValueError("Cannot generate MCQ without evidence (zero hallucinations policy)")
    
    # Extract citations
    citations = []
    for ev in evidence:
        if doc_metadata.get("pmid"):
            citations.append(f"PMID:{doc_metadata['pmid']}")
        elif doc_metadata.get("doi"):
            citations.append(f"DOI:{doc_metadata['doi']}")
    
    # Stub: return minimal structure
    return {
        "stem": "",
        "options_json": "[]",
        "explanation": "",
        "citations_json": str(citations) if citations else "[]"
    }


def validate_mcq(mcq: Dict[str, Any], evidence: List[Dict[str, Any]]) -> bool:
    """
    Validate MCQ against quality gates (citation presence, evidence leakage, etc.).
    
    Args:
        mcq: MCQ dictionary
        evidence: List of evidence dictionaries
        
    Returns:
        True if valid, False otherwise
    """
    # Check citation presence
    citations_json = mcq.get("citations_json", "[]")
    if not citations_json or citations_json == "[]":
        return False
    
    # Stub: return True for now
    return True

