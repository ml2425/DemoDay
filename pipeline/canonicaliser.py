"""
Canonicalization module.
Maps variable medical expressions to unified canonical concepts.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

from providers.llm_adapter import LLMAdapter
from database.entity_utils import upsert_concept, insert_entity
from utils.cache import hash_key, cache_get, cache_set

logger = logging.getLogger(__name__)


class CanonicaliserNode:
    """
    Canonicalization node with LLM adapter and database caching.
    """
    
    def __init__(self, conn: sqlite3.Connection, adapter: Optional[LLMAdapter] = None):
        """
        Initialize canonicalizer node.
        
        Args:
            conn: Database connection
            adapter: Optional LLM adapter (creates default if None)
        """
        self.conn = conn
        self.adapter = adapter or LLMAdapter()
    
    def canonicalize(self, span: str, sentence: str) -> Dict[str, Any]:
        """
        Canonicalize an entity span using cache first, then adapter.
        
        Args:
            span: Entity text span
            sentence: Context sentence
            
        Returns:
            Dict with canonical_name, semantic_category, confidence
        """
        # Build cache key
        cache_key = f"canon|{hash_key(span, sentence)}"
        
        # Check cache first
        cached_value = cache_get(self.conn, cache_key)
        if cached_value:
            return json.loads(cached_value)
        
        # Call adapter (LLM or heuristic)
        result = self.adapter.canonicalize(span, sentence)
        
        # Write back to cache
        cache_set(self.conn, cache_key, json.dumps(result))
        
        return result
    
    def process_spans(self, doc_id: int, sent_idx: int, spans: List[Tuple[int, int, str]], sentence: str = "") -> List[int]:
        """
        Process entity spans: canonicalize, upsert concepts, insert entities.
        
        Args:
            doc_id: Document ID
            sent_idx: Sentence index
            spans: List of (char_start, char_end, span_text) tuples
            sentence: Full sentence text for context (optional)
            
        Returns:
            List of entity_id values for inserted entities
        """
        entity_ids = []
        
        for char_start, char_end, span_text in spans:
            # Canonicalize
            canonical = self.canonicalize(span_text, sentence)
            
            # CRITICAL: Skip negated entities (prevents false positives)
            if canonical.get("semantic_category") == "NONE" or canonical.get("canonical_name") == "NEGATED":
                logger.info(f"Skipping NEGATED entity: '{span_text}'")
                continue  # Do NOT insert entity or concept
            
            # Upsert concept
            canonical_id = upsert_concept(
                self.conn,
                canonical["canonical_name"],
                canonical["semantic_category"],
                canonical["confidence"]
            )
            
            # Insert entity
            entity_id = insert_entity(
                self.conn,
                canonical_id,
                doc_id,
                sent_idx,
                char_start,
                char_end,
                span_text
            )
            
            entity_ids.append(entity_id)
        
        return entity_ids

