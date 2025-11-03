"""
Relation verification module.
LLM validates that evidence supports extracted triples.
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from providers.llm_adapter import LLMAdapter
from utils.cache import hash_key, cache_get, cache_set


class RelationVerifierNode:
    """
    Relation verifier node with LLM adapter and database caching.
    """
    
    def __init__(self, conn: sqlite3.Connection, adapter: Optional[LLMAdapter] = None):
        """
        Initialize relation verifier node.
        
        Args:
            conn: Database connection
            adapter: Optional LLM adapter (creates default if None)
        """
        self.conn = conn
        self.adapter = adapter or LLMAdapter()
        self.verifier_model = "heuristic"  # Will be LLM model name when implemented
    
    def verify(self, sentence: str, triple: Tuple[str, str, str]) -> Dict[str, Any]:
        """
        Verify that a triple is entailed by the sentence.
        
        Args:
            sentence: Evidence sentence text
            triple: Tuple of (head_name, rel_id, tail_name)
            
        Returns:
            Dict with keys: entailed (bool), confidence (float), reasoning (str)
        """
        head_name, rel_id, tail_name = triple
        
        # Build cache key
        cache_key = f"verify|{hash_key(sentence, head_name, rel_id, tail_name)}"
        
        # Check cache first
        cached_value = cache_get(self.conn, cache_key)
        if cached_value:
            return json.loads(cached_value)
        
        # Deterministic fallback verification
        sentence_lower = sentence.lower()
        head_lower = head_name.lower()
        tail_lower = tail_name.lower()
        
        # Check if both entities appear in sentence
        head_present = head_lower in sentence_lower
        tail_present = tail_lower in sentence_lower
        
        # Relation-specific keyword checks
        rel_keywords = {
            "TREATS": r'\b(?:treat|therapy|therapeutic|first-line|manages?)\b',
            "CAUSES": r'\b(?:cause|causes|caused\s+by|leading\s+to)\b',
            "HAS_FINDING": r'\b(?:has|with|presents?|exhibits?)\b',
            "INVESTIGATED_BY": r'\b(?:ct|mri|scan|imaging|detected\s+by)\b'
        }
        
        keyword_present = False
        if rel_id in rel_keywords:
            import re
            keyword_present = bool(re.search(rel_keywords[rel_id], sentence_lower))
        
        # Deterministic fallback logic
        if head_present and tail_present and keyword_present:
            result = {
                "entailed": True,
                "confidence": 0.75,
                "reasoning": f"Both entities found in sentence with relation keyword"
            }
        else:
            result = {
                "entailed": False,
                "confidence": 0.25,
                "reasoning": f"Missing entities or relation keyword"
            }
        
        # Write back to cache
        cache_set(self.conn, cache_key, json.dumps(result), cache_type="verification")
        
        return result

