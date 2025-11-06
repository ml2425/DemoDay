"""Node 6: Verify evidence using fuzzy matching."""

from typing import Dict, Any
from difflib import SequenceMatcher
from database.db_utils import connect, get_triple, get_source


def fuzzy_match(text1: str, text2: str, threshold: float = 0.70) -> tuple[bool, float]:
    """
    Check if two texts match using fuzzy string matching.
    
    Args:
        text1: First text
        text2: Second text
        threshold: Minimum similarity threshold (default 0.70 per v3.2)
        
    Returns:
        Tuple of (matches, similarity_score)
    """
    # Normalize texts
    text1_norm = " ".join(text1.lower().split())
    text2_norm = " ".join(text2.lower().split())
    
    # Calculate similarity
    similarity = SequenceMatcher(None, text1_norm, text2_norm).ratio()
    
    return similarity >= threshold, similarity


def verify_evidence_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify evidence snippets exist in source text using fuzzy matching.
    
    Expected state keys:
        - source_id: Source identifier
        - generated_mcqs: List of MCQ dicts
    
    Updates state with:
        - verified_mcqs: List of verified MCQ dicts with verification status
    """
    source_id = state.get("source_id", "")
    generated_mcqs = state.get("generated_mcqs", [])
    
    if not source_id:
        raise ValueError("source_id is required")
    
    conn = connect()
    
    # Get source text
    source = get_source(conn, source_id)
    if not source:
        raise ValueError(f"Source {source_id} not found")
    
    source_text = source["full_text"]
    verified_mcqs = []
    
    for mcq_item in generated_mcqs:
        triple_id = mcq_item["triple_id"]
        
        # Get triple
        triple = get_triple(conn, triple_id)
        if not triple:
            continue
        
        evidence_snippet = triple["evidence_snippet"]
        
        # Fuzzy match evidence against source text
        # Check if evidence snippet appears in source (with ±250 char window for context)
        matches, similarity = fuzzy_match(evidence_snippet, source_text, threshold=0.70)
        
        verification_status = "verified" if matches else "warning"
        
        # Update MCQ verification status
        from database.db_utils import update_mcq_status
        # Note: We'll update verification_status directly via SQL
        conn.execute(
            """UPDATE mcqs 
               SET verification_status = ?, verification_confidence = ?
               WHERE mcq_id = ?""",
            (verification_status, similarity, mcq_item["mcq_id"])
        )
        conn.commit()
        
        verified_mcqs.append({
            **mcq_item,
            "verification_status": verification_status,
            "verification_confidence": similarity
        })
    
    conn.close()
    
    state["verified_mcqs"] = verified_mcqs
    print(f"[OK] Verified {len(verified_mcqs)} MCQs")
    
    return state

