"""
Relation extraction package.
Provides LLM-based extraction with schema constraints.
"""

import sqlite3
from typing import List, Dict, Optional
from .extractor import extract_relations_llm_with_schema
from .schema_loader import RelationSchema

class RelationExtractor:
    """
    LLM-based relation extraction with schema constraints.
    Returns Dict format with head, relation, tail, confidence, and evidence.
    """
    
    def __init__(self, domain: str = "neurosurgery", conn: Optional[sqlite3.Connection] = None):
        self.domain = domain
        self.conn = conn
    
    def candidates(self, sentence: str, entities: List[Dict]) -> List[Dict]:
        """
        Extract candidates using LLM (with schema constraints).
        
        Args:
            sentence: Sentence text
            entities: List of entity dicts with keys: entity_id, name, type, span_text
            
        Returns:
            List of dicts with keys: head, relation, tail, confidence, evidence
        """
        return extract_relations_llm_with_schema(
            sentence, entities, domain=self.domain, conn=self.conn
        )

# Export for usage
__all__ = ["RelationExtractor", "extract_relations_llm_with_schema", "RelationSchema"]

