"""
LLM adapter providing unified interface for canonicalization.
Supports multiple providers with offline heuristic fallback.
"""

import os
import re
from typing import Dict, Any, Optional
from utils.runtime import get_config


def _heuristic_canonicalize(span: str, sentence: str) -> Dict[str, Any]:
    """
    Deterministic heuristic fallback when LLM keys are missing.
    
    Simple pattern-based classification:
    - "-itis" endings → DISORDER
    - "MRI/CT" mentions → INVESTIGATION
    - Drug suffixes "-pril/-mab/-azole" → DRUG
    - "resection/ectomy" → PROCEDURE
    - Default → FINDING
    """
    span_lower = span.lower()
    sentence_lower = sentence.lower()
    
    # DISORDER: inflammatory conditions
    if re.search(r'itis$', span_lower, re.IGNORECASE):
        return {
            "canonical_name": span.strip(),
            "semantic_category": "DISORDER",
            "confidence": 0.5
        }
    
    # INVESTIGATION: imaging/scan terms
    if re.search(r'\b(?:mri|ct|scan|ultrasound|x-ray|pet|spect)\b', sentence_lower):
        if any(term in span_lower for term in ['mri', 'ct', 'scan', 'imaging']):
            return {
                "canonical_name": span.strip(),
                "semantic_category": "INVESTIGATION",
                "confidence": 0.6
            }
    
    # DRUG: common drug suffixes
    if re.search(r'(?:pril|mab|azole|mycin|olol|prazole|dipine)$', span_lower, re.IGNORECASE):
        return {
            "canonical_name": span.strip(),
            "semantic_category": "DRUG",
            "confidence": 0.5
        }
    
    # PROCEDURE: surgical terms
    if re.search(r'\b(?:resection|ectomy|otomy|plasty|stomy|centesis)\b', span_lower):
        return {
            "canonical_name": span.strip(),
            "semantic_category": "PROCEDURE",
            "confidence": 0.5
        }
    
    # Default: FINDING
    return {
        "canonical_name": span.strip(),
        "semantic_category": "FINDING",
        "confidence": 0.4
    }


class LLMAdapter:
    """
    Unified LLM adapter for canonicalization.
    Falls back to heuristics if API keys are missing.
    """
    
    def __init__(self):
        """Initialize adapter, check for API keys."""
        self.provider = get_config("llm.provider", "openai")
        self.model = get_config("llm.canonicalizer_model", "gpt-4o-mini")
        self.temperature = 0
        
        # Check for API keys
        self.has_keys = False
        if self.provider == "openai":
            api_key = get_config("providers.openai_api_key") or os.getenv("OPENAI_API_KEY")
            self.has_keys = bool(api_key)
    
    def canonicalize(self, span: str, sentence: str) -> Dict[str, Any]:
        """
        Canonicalize an entity span to a canonical concept.
        
        Args:
            span: Entity text span
            sentence: Context sentence
            
        Returns:
            Dict with keys: canonical_name, semantic_category, confidence
        """
        # If no API keys, use heuristic fallback
        if not self.has_keys:
            return _heuristic_canonicalize(span, sentence)
        
        # TODO: Implement actual LLM calls (OpenAI, Anthropic, etc.)
        # For now, fall back to heuristic
        return _heuristic_canonicalize(span, sentence)

