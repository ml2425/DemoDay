"""
Negation detection module.
Filters out negated mentions before expensive LLM calls.

Policy: Drop negated mentions (v1.2)
Sentences containing negation cues (e.g., "no evidence of", "ruled out") are
filtered out before entity extraction to prevent false positive extractions.
This conservative approach ensures only affirmative statements enter the KG.
"""

from typing import List
import sqlite3

from database.negation_utils import detect_negations, write_negations


class NegationNode:
    """
    Negation detection and filtering node.
    
    Implements v1.2 policy: detects negated mentions using regex patterns
    and filters them out before expensive LLM canonicalization calls.
    """
    
    def filter(self, doc_id: int, sentences: List[str], conn: sqlite3.Connection) -> List[str]:
        """
        Filter out negated sentences and log them to database.
        
        Args:
            doc_id: Document ID
            sentences: List of sentence strings to filter
            conn: Database connection
            
        Returns:
            List of kept sentences (negated sentences removed)
        """
        # Detect negations
        kept_sentences, negations = detect_negations(sentences)
        
        # Write negations to database for logging
        if negations:
            write_negations(conn, doc_id, negations)
        
        return kept_sentences

