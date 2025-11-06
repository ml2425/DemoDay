"""
Span detection module.
Finds entity spans in sentences using deterministic regex patterns.
"""

import re
from typing import List, Tuple

# Common English stop words that appear capitalized at sentence starts
# These should NOT be treated as medical entities
_STOP_WORDS = {
    # Pronoun/determiners
    "this", "that", "these", "those",
    "the", "a", "an",
    "his", "her", "its", "their", "our", "your", "my",
    "he", "she", "it", "they", "we", "you", "i",
    
    # Common sentence starters
    "however", "therefore", "thus", "hence", "furthermore", "moreover",
    "although", "because", "since", "while", "when",
    "first", "second", "third", "last", "next", "then", "finally",
    
    # Common medical text words (non-entities)
    "treatment", "standard", "therapy", "approach", "method", "technique",
    "group", "study", "patient", "patients", "case", "cases",
    "result", "results", "finding", "findings", "data", "analysis",
    "clinical", "medical", "surgical", "diagnostic", "therapeutic",
    "procedure", "procedures", "intervention", "interventions",
    "trial", "trials", "research", "investigation", "investigations",
    
    # Time/place words
    "time", "times", "period", "periods", "year", "years",
    "month", "months", "week", "weeks", "day", "days",
    
    # Common verbs (when capitalized)
    "may", "can", "could", "should", "would", "will", "shall",
    "is", "are", "was", "were", "been", "being", "have", "has", "had",
    
    # Common adjectives
    "important", "significant", "common", "rare", "typical", "atypical",
    "present", "absent", "positive", "negative", "high", "low",
}


def _is_stop_word(span_text: str) -> bool:
    """
    Check if a span is a common stop word that should be filtered.
    
    Args:
        span_text: The span text to check
        
    Returns:
        True if span should be filtered out
    """
    span_lower = span_text.lower()
    return span_lower in _STOP_WORDS


def find_spans(sentence: str) -> List[Tuple[int, int, str]]:
    """
    Find entity spans in a sentence using deterministic regex patterns.
    
    Returns character-indexed spans (char_start, char_end, span_text)
    where char_end is exclusive.
    
    Patterns:
    - Multiword: type 2 diabetes, subarachnoid hemorrhage, glioblastoma
    - Single tokens: capitalized words (length≥3)
    - Medical suffixes: -itis, -osis, -oma, -emia
    - Investigations: MRI, CT, angiography, ultrasound, EEG, ECG, PET, x-ray
    
    Args:
        sentence: Input sentence text
        
    Returns:
        List of tuples: (char_start, char_end, span_text)
        char_end is exclusive (Python slice style)
    """
    spans = []
    sentence_lower = sentence.lower()
    
    # Multiword patterns (case-insensitive)
    multiword_patterns = [
        (r'\btype\s+\d+\s+diabetes\b', 'type 2 diabetes'),  # Simplified - matches "type 2" or "type 1"
        (r'\btype\s+[12]\s+diabetes\b', 'type N diabetes'),
        (r'\bsubarachnoid\s+hemorrhage\b', 'subarachnoid hemorrhage'),
        (r'\bglioblastoma\b', 'glioblastoma'),
        (r'\bmyocardial\s+infarction\b', 'myocardial infarction'),
        (r'\bheart\s+failure\b', 'heart failure'),
        (r'\bpulmonary\s+embolism\b', 'pulmonary embolism'),
    ]
    
    for pattern, _ in multiword_patterns:
        for match in re.finditer(pattern, sentence_lower):
            # Find original case in sentence
            start = match.start()
            end = match.end()
            span_text = sentence[start:end]
            spans.append((start, end, span_text))
    
    # Single tokens: capitalized words (length >= 3)
    # Match words that start with uppercase letter and have at least 3 chars
    capitalized_pattern = r'\b[A-Z][a-z]{2,}\b'
    for match in re.finditer(capitalized_pattern, sentence):
        start = match.start()
        end = match.end()
        span_text = sentence[start:end]
        # Exclude if already captured as multiword
        if not any(s[0] <= start < s[1] or s[0] < end <= s[1] for s in spans):
            spans.append((start, end, span_text))
    
    # Medical suffixes: -itis, -osis, -oma, -emia
    suffix_pattern = r'\b\w+(?:itis|osis|oma|emia)\b'
    for match in re.finditer(suffix_pattern, sentence, re.IGNORECASE):
        start = match.start()
        end = match.end()
        span_text = sentence[start:end]
        # Exclude if already captured
        if not any(s[0] <= start < s[1] or s[0] < end <= s[1] for s in spans):
            spans.append((start, end, span_text))
    
    # Investigations: MRI, CT, angiography, ultrasound, EEG, ECG, PET, x-ray
    investigation_patterns = [
        r'\b(?:MRI|CT|EEG|ECG|PET)\b',
        r'\b(?:angiography|ultrasound|x-ray)\b'
    ]
    
    for pattern in investigation_patterns:
        for match in re.finditer(pattern, sentence, re.IGNORECASE):
            start = match.start()
            end = match.end()
            span_text = sentence[start:end]
            # Exclude if already captured
            if not any(s[0] <= start < s[1] or s[0] < end <= s[1] for s in spans):
                spans.append((start, end, span_text))
    
    # Remove duplicates and sort by start position
    unique_spans = []
    seen = set()
    for span in sorted(spans, key=lambda x: x[0]):
        if (span[0], span[1]) not in seen:
            seen.add((span[0], span[1]))
            unique_spans.append(span)
    
    # Filter out stop words (prevents LLM calls for common words like "This", "The")
    filtered_spans = [
        span for span in unique_spans 
        if not _is_stop_word(span[2])  # span[2] is the span_text
    ]
    
    return filtered_spans

