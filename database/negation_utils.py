"""
Negation detection utilities.
Provides regex-based negation detection and database logging.
"""

import re
from typing import List, Dict, Tuple
import sqlite3


# Common medical negation patterns
NEGATION_PATTERNS = [
    (r'\bno\s+evidence\s+of\b', 'no evidence of'),
    (r'\bnegative\s+for\b', 'negative for'),
    (r'\bruled\s+out\b', 'ruled out'),
    (r'\bwithout\s+(?:evidence\s+of|signs\s+of|indication\s+of)\b', 'without'),
    (r'\bdid\s+not\s+show\b', 'did not show'),
    (r'\bdid\s+not\s+demonstrate\b', 'did not demonstrate'),
    (r'\bfailed\s+to\s+show\b', 'failed to show'),
    (r'\babsence\s+of\b', 'absence of'),
    (r'\blacked\s+evidence\s+of\b', 'lacked evidence of'),
    (r'\bdenies\s+(?:history\s+of|presence\s+of)\b', 'denies'),
    (r'\bexcluded\b', 'excluded'),
    (r'\bnot\s+(?:present|identified|found|detected|observed)\b', 'not'),
]


def detect_negations(sentences: List[str]) -> Tuple[List[str], List[Dict]]:
    """
    Detect negated mentions in sentences using regex patterns.
    
    Implements v1.2 policy: sentences containing negation cues are filtered out
    before expensive LLM calls to prevent false positive entity extractions.
    
    Args:
        sentences: List of sentence strings
        
    Returns:
        Tuple of (kept_sentences, negations) where:
        - kept_sentences: List of sentences without negations
        - negations: List of dicts with keys: sent_idx, span_text, cue_text, context_sentence
    """
    kept_sentences = []
    negations = []
    
    for sent_idx, sentence in enumerate(sentences):
        is_negated = False
        detected_cue = None
        detected_span = None
        
        # Check each negation pattern
        for pattern, cue_name in NEGATION_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                is_negated = True
                detected_cue = cue_name
                # Extract a reasonable span around the match (50 chars before/after)
                start = max(0, match.start() - 50)
                end = min(len(sentence), match.end() + 50)
                detected_span = sentence[start:end].strip()
                break
        
        if is_negated:
            # Add to negations log
            negations.append({
                'sent_idx': sent_idx,
                'span_text': detected_span or sentence[:100],  # Truncate if needed
                'cue_text': detected_cue,
                'context_sentence': sentence
            })
        else:
            # Keep the sentence
            kept_sentences.append(sentence)
    
    return (kept_sentences, negations)


def write_negations(conn: sqlite3.Connection, doc_id: int, negations: List[Dict]) -> int:
    """
    Write negation records to the negations table.
    
    Args:
        conn: Database connection
        doc_id: Document ID
        negations: List of negation dictionaries with sent_idx, span_text, cue_text, context_sentence
        
    Returns:
        Number of negations written
    """
    if not negations:
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for neg in negations:
        cursor.execute(
            """
            INSERT INTO negations (doc_id, sent_idx, span_text, cue_text, context_sentence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                neg.get('sent_idx'),
                neg.get('span_text', ''),
                neg.get('cue_text', ''),
                neg.get('context_sentence', '')
            )
        )
        count += 1
    
    conn.commit()
    return count

