"""
Negation detection module.
Filters out negated mentions before expensive LLM calls.
"""

from typing import List, Dict, Any


def detect_negations(sentences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect negated mentions in sentences using pattern matching.
    
    Args:
        sentences: List of sentence dictionaries
        
    Returns:
        List of negation dictionaries with 'sent_idx', 'span_text', 'cue_text'
    """
    # Stub: return empty list
    return []


def is_negated(text: str) -> bool:
    """
    Check if a text span contains negation cues.
    
    Args:
        text: Text to check
        
    Returns:
        True if negated, False otherwise
    """
    # Stub: return False
    return False

