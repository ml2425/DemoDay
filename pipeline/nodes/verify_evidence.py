"""Node 6: Verify evidence using hybrid matching (substring + sliding window + semantic)."""

from typing import Dict, Any, Tuple
from difflib import SequenceMatcher
import numpy as np
import os
from openai import OpenAI
from dotenv import load_dotenv
from database.db_utils import connect, get_triple, get_source

load_dotenv()


def exact_substring_match(evidence_snippet: str, source_text: str) -> Tuple[bool, float]:
    """
    Check for exact substring match (fastest, 100% confidence).
    
    Returns:
        (found, confidence)
    """
    evidence_norm = " ".join(evidence_snippet.lower().split())
    source_norm = " ".join(source_text.lower().split())
    
    if evidence_norm in source_norm:
        return True, 1.0
    return False, 0.0


def fuzzy_substring_match(evidence_snippet: str, source_text: str, threshold: float = 0.70) -> Tuple[bool, float]:
    """
    Find best match using sliding window with SequenceMatcher.
    
    Returns:
        (matches, best_similarity_score)
    """
    evidence_norm = " ".join(evidence_snippet.lower().split())
    source_norm = " ".join(source_text.lower().split())
    
    snippet_len = len(evidence_norm)
    if snippet_len == 0:
        return False, 0.0
    
    # Sliding window: try windows of 1x, 1.5x, 2x snippet length
    window_multipliers = [1.0, 1.5, 2.0]
    best_similarity = 0.0
    
    for multiplier in window_multipliers:
        window_size = int(snippet_len * multiplier)
        window_size = min(window_size, len(source_norm))
        
        # Slide window through source text
        for i in range(len(source_norm) - window_size + 1):
            window = source_norm[i:i + window_size]
            similarity = SequenceMatcher(None, evidence_norm, window).ratio()
            
            if similarity > best_similarity:
                best_similarity = similarity
    
    return best_similarity >= threshold, best_similarity


def semantic_similarity_cosine(evidence_snippet: str, source_text: str, threshold: float = 0.70) -> Tuple[bool, float]:
    """
    Calculate semantic similarity using cosine similarity of OpenAI embeddings.
    Uses sliding window to find best matching segment in source text.
    Batches embeddings for efficiency.
    
    Returns:
        (matches, cosine_similarity_score)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, 0.0
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Get embedding for evidence snippet
        evidence_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[evidence_snippet]
        )
        evidence_embedding = np.array(evidence_response.data[0].embedding)
        
        # Sliding window: split source into overlapping chunks
        words = source_text.split()
        snippet_word_count = len(evidence_snippet.split())
        
        # Create windows: try 1x and 2x snippet length (limit to reasonable number)
        window_sizes = [
            min(snippet_word_count, len(words)),
            min(snippet_word_count * 2, len(words))
        ]
        
        # Collect all windows to batch embed
        windows = []
        window_positions = []
        
        for window_size in window_sizes:
            if window_size == 0:
                continue
            step = max(1, window_size // 2)  # 50% overlap
            
            # Limit to max 20 windows to avoid too many API calls
            for i in range(0, min(len(words) - window_size + 1, 20 * step), step):
                window_text = " ".join(words[i:i + window_size])
                windows.append(window_text)
                window_positions.append((i, i + window_size))
        
        if not windows:
            return False, 0.0
        
        # Batch embed all windows at once
        windows_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=windows
        )
        
        # Calculate cosine similarity for each window
        best_similarity = 0.0
        for window_embedding_data in windows_response.data:
            window_embedding = np.array(window_embedding_data.embedding)
            
            cosine_sim = np.dot(evidence_embedding, window_embedding) / (
                np.linalg.norm(evidence_embedding) * np.linalg.norm(window_embedding)
            )
            
            if cosine_sim > best_similarity:
                best_similarity = cosine_sim
        
        return best_similarity >= threshold, float(best_similarity)
    except Exception as e:
        print(f"[WARN] OpenAI embedding failed: {e}, falling back to fuzzy match")
        return False, 0.0


def verify_evidence_hybrid(evidence_snippet: str, source_text: str, threshold: float = 0.70) -> Dict[str, Any]:
    """
    Hybrid verification: exact → fuzzy → semantic.
    
    Returns:
        {
            "verified": bool,
            "confidence": float,
            "method": str ("exact", "fuzzy", "semantic", "failed")
        }
    """
    # Tier 1: Exact substring match (fastest, 100% confidence)
    found, confidence = exact_substring_match(evidence_snippet, source_text)
    if found:
        return {
            "verified": True,
            "confidence": confidence,
            "method": "exact"
        }
    
    # Tier 2: Fuzzy substring with sliding window
    found, confidence = fuzzy_substring_match(evidence_snippet, source_text, threshold)
    if found:
        return {
            "verified": True,
            "confidence": confidence,
            "method": "fuzzy"
        }
    
    # Tier 3: Semantic similarity (only if fuzzy fails, more expensive)
    # Use semantic similarity for paraphrased/restructured text
    found, confidence = semantic_similarity_cosine(evidence_snippet, source_text, threshold)
    if found:
        return {
            "verified": True,
            "confidence": confidence,
            "method": "semantic"
        }
    
    # All methods failed - return best confidence from fuzzy match
    _, best_fuzzy_confidence = fuzzy_substring_match(evidence_snippet, source_text, threshold=0.0)
    return {
        "verified": False,
        "confidence": best_fuzzy_confidence,
        "method": "failed"
    }


def verify_evidence_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify evidence snippets exist in source text using hybrid matching.
    
    Uses 3-tier approach:
    1. Exact substring match (fastest, 100% confidence)
    2. Fuzzy substring with sliding window (SequenceMatcher)
    3. Semantic similarity with cosine similarity (OpenAI embeddings)
    
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
        
        # Hybrid verification: exact → fuzzy → semantic
        result = verify_evidence_hybrid(evidence_snippet, source_text, threshold=0.70)
        
        verification_status = "verified" if result["verified"] else "warning"
        confidence = result["confidence"]
        
        # Update MCQ verification status
        conn.execute(
            """UPDATE mcqs 
               SET verification_status = ?, verification_confidence = ?
               WHERE mcq_id = ?""",
            (verification_status, confidence, mcq_item["mcq_id"])
        )
        conn.commit()
        
        verified_mcqs.append({
            **mcq_item,
            "verification_status": verification_status,
            "verification_confidence": confidence,
            "verification_method": result["method"]
        })
        
        print(f"[DEBUG] MCQ {mcq_item['mcq_id']}: {result['method']} match, confidence={confidence:.2f}")
    
    conn.close()
    
    state["verified_mcqs"] = verified_mcqs
    print(f"[OK] Verified {len(verified_mcqs)} MCQs")
    
    return state

