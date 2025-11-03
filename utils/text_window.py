"""
Text window utilities for evidence extraction.
Builds multi-sentence windows around a center sentence.
"""

from typing import Tuple, List


def build_window(
    sentences: List[str],
    center_idx: int,
    max_sentences: int = 3
) -> Tuple[int, int, str]:
    """
    Build a sentence window centered around center_idx.
    
    Returns indices and joined text where end_idx - start_idx < max_sentences.
    Uses zero-based inclusive indices. Joins sentences with a single space.
    
    Args:
        sentences: List of sentence strings
        center_idx: Center sentence index (0-based)
        max_sentences: Maximum number of sentences in window (default: 3)
        
    Returns:
        Tuple of (start_idx, end_idx, joined_text)
        where end_idx - start_idx < max_sentences (inclusive range)
    """
    if not sentences:
        return (0, 0, "")
    
    # Clamp center_idx to valid range
    center_idx = max(0, min(center_idx, len(sentences) - 1))
    
    # Calculate window boundaries
    # We want at most max_sentences, so end - start < max_sentences
    # For max_sentences=3, we can have indices like: [0,1,2] (3 sentences, diff=2)
    # Or [0,1] (2 sentences, diff=1)
    
    # Start with center sentence
    start_idx = center_idx
    end_idx = center_idx
    
    # Expand window symmetrically, respecting bounds
    while (end_idx - start_idx + 1) < max_sentences:
        can_expand_left = start_idx > 0
        can_expand_right = end_idx < len(sentences) - 1
        
        # Prefer expanding left first (before center)
        if can_expand_left:
            start_idx -= 1
        elif can_expand_right:
            end_idx += 1
        else:
            break
        
        # Ensure constraint: end_idx - start_idx < max_sentences
        if (end_idx - start_idx) >= max_sentences:
            # Roll back last expansion
            if start_idx < center_idx:
                start_idx += 1
            elif end_idx > center_idx:
                end_idx -= 1
            break
    
    # Extract window sentences and join with single space
    window_sentences = sentences[start_idx:end_idx + 1]
    joined_text = " ".join(window_sentences)
    
    return (start_idx, end_idx, joined_text)

