"""
LLM adapter providing unified interface for canonicalization.
Supports multiple providers with offline heuristic fallback.
"""

import os
import json
import re
import logging
from typing import Dict, Any, Optional
from utils.runtime import get_config

# CRITICAL: Add logger to prevent NameError
logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# CRITICAL: Include "NONE" for negation sentinel
ALLOWED_CATEGORIES = {"DISORDER", "DRUG", "FINDING", "INVESTIGATION", "PROCEDURE", "MICROBE", "NONE"}


def _build_enhanced_fewshot_prompt(span: str, sentence: str) -> str:
    """12-example few-shot prompt with negation handling"""
    return f"""You are a medical entity canonicalization system.

**Task:** Normalize medical terminology and classify into semantic categories.

**Canonicalization Rules:**
1. Use standard medical terminology (not lay terms)
2. Expand abbreviations to full medical names (MRI → Magnetic Resonance Imaging)
3. Use title case (Temozolomide, not temozolomide)
4. Normalize synonyms to ONE canonical form (heart attack → Myocardial Infarction)
5. Correct minor typos to standard spelling
6. Prefer specific over general (Glioblastoma, not Brain Tumor)

**Categories:**
- DISORDER: Disease/condition needing treatment (glioblastoma, myocardial infarction)
- FINDING: Observable sign/symptom (headache, fever, papilledema)
- DRUG: Medication (temozolomide, aspirin)
- INVESTIGATION: Diagnostic test (MRI, biopsy, blood culture)
- PROCEDURE: Medical intervention (resection, angioplasty)
- MICROBE: Pathogenic organism (S. aureus, E. coli)

**CRITICAL - FINDING vs DISORDER:**
- FINDING: Observation/symptom (e.g., "headache" is a symptom)
- DISORDER: Primary pathology (e.g., "glioblastoma" is the disease)
- If both apply, prefer DISORDER when term represents disease entity

**Negation Rule:**
If sentence negates the span ("no tumor", "denies headache", "absent"), return:
{{"canonical_name": "NEGATED", "semantic_category": "NONE", "confidence": 0.0}}

**Confidence:**
- High (0.85-1.0): Unambiguous with clear context
- Medium (0.65-0.84): Slightly ambiguous, context clarifies
- Low (0.0-0.64): Ambiguous or unclear

**Output:** JSON only, no explanation.

---

**Example 1: Basic DISORDER**
span: "glioma"
sentence: "Diffuse glioma is treated with temozolomide and radiotherapy."
{{"canonical_name": "Glioma", "semantic_category": "DISORDER", "confidence": 0.92}}

**Example 2: DRUG**
span: "temozolomide"
sentence: "Diffuse glioma is treated with temozolomide and radiotherapy."
{{"canonical_name": "Temozolomide", "semantic_category": "DRUG", "confidence": 0.95}}

**Example 3: INVESTIGATION (expand abbreviation)**
span: "MRI"
sentence: "MRI is used to assess postoperative changes and recurrence."
{{"canonical_name": "Magnetic Resonance Imaging", "semantic_category": "INVESTIGATION", "confidence": 0.90}}

**Example 4: PROCEDURE**
span: "resection"
sentence: "Gross total resection improves outcomes when feasible."
{{"canonical_name": "Surgical Resection", "semantic_category": "PROCEDURE", "confidence": 0.89}}

**Example 5: FINDING (symptom)**
span: "headache"
sentence: "The patient reported a two-week history of worsening headache."
{{"canonical_name": "Headache", "semantic_category": "FINDING", "confidence": 0.88}}

**Example 6: Abbreviation disambiguation (cardiac context)**
span: "MI"
sentence: "ECG shows ST elevation. Troponin elevated. Diagnosed with MI."
{{"canonical_name": "Myocardial Infarction", "semantic_category": "DISORDER", "confidence": 0.91}}

**Example 7: Synonym normalization (lay → medical)**
span: "heart attack"
sentence: "Patient suffered a heart attack and was rushed to ER."
{{"canonical_name": "Myocardial Infarction", "semantic_category": "DISORDER", "confidence": 0.86}}

**Example 8: Multi-word span**
span: "gross total resection"
sentence: "Maximal safe gross total resection was achieved."
{{"canonical_name": "Gross Total Resection", "semantic_category": "PROCEDURE", "confidence": 0.93}}

**Example 9: Context distinguishes DISORDER from FINDING**
span: "mass"
sentence: "MRI revealed an enhancing mass in the right frontal lobe."
{{"canonical_name": "Brain Neoplasm", "semantic_category": "DISORDER", "confidence": 0.85}}

**Example 10: Typo correction**
span: "temozolamide"
sentence: "Treated with temozolamide and radiation therapy."
{{"canonical_name": "Temozolomide", "semantic_category": "DRUG", "confidence": 0.82}}

**Example 11: Negation detection**
span: "tumor"
sentence: "Follow-up MRI showed no evidence of residual tumor."
{{"canonical_name": "NEGATED", "semantic_category": "NONE", "confidence": 0.0}}

**Example 12: MICROBE with full nomenclature**
span: "S. aureus"
sentence: "Blood cultures grew S. aureus resistant to methicillin."
{{"canonical_name": "Staphylococcus aureus", "semantic_category": "MICROBE", "confidence": 0.94}}

---

**Now classify:**
span: "{span}"
sentence: "{sentence}"

**Output (JSON only):**""".strip()


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from response (handles text-wrapped JSON)"""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except:
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"No JSON in response: {text[:200]}")


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
    
    # DISORDER: common disorder terms
    if re.search(r'\b(?:diabetes|migraine|hypertension|pneumonia|meningitis|epilepsy)\b', span_lower):
        return {
            "canonical_name": span.strip(),
            "semantic_category": "DISORDER",
            "confidence": 0.5
        }
    
    # DRUG: common drug suffixes and names
    if re.search(r'(?:pril|mab|azole|mycin|olol|prazole|dipine|formin|in|ol|ide)$', span_lower, re.IGNORECASE):
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
    
    def _call_openai_canonicalize(self, span: str, sentence: str, timeout_s: float = 30.0) -> Dict[str, Any]:
        """
        Call OpenAI with enhanced prompt and validation.
        
        Returns sentinel {"canonical_name": "NEGATED", "semantic_category": "NONE", "confidence": 0.0}
        if negation detected.
        """
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            try:
                from utils.runtime import get_config
                api_key = get_config("providers.openai_api_key")
            except:
                pass
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing")
        
        # FIXED: Timeout on client level removed (SDK compatibility issue)
        client = OpenAI(api_key=api_key)
        prompt = _build_enhanced_fewshot_prompt(span, sentence)
        
        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": "You are a medical entity classification system. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                timeout=timeout_s  # FIXED: Timeout on request level
            )
            
            content = resp.choices[0].message.content if resp and resp.choices else ""
            data = _extract_json(content)
            
            # Validate and normalize
            cname = str(data.get("canonical_name", "")).strip()
            cat = str(data.get("semantic_category", "")).strip().upper()
            conf = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
            
            # FIXED: "NONE" now allowed in validation (negation sentinel)
            if not cname or cat not in ALLOWED_CATEGORIES:
                raise ValueError(f"Invalid response: cname='{cname}' cat='{cat}'")
            
            return {"canonical_name": cname, "semantic_category": cat, "confidence": conf}
            
        except Exception as e:
            raise TimeoutError(f"OpenAI call failed: {e}")
    
    def _validate_canonicalization(self, span: str, canonical_name: str) -> bool:
        """Post-validation to catch hallucinations"""
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, span.lower(), canonical_name.lower()).ratio()
        
        # Low similarity might be hallucination (unless known abbreviation)
        # Relaxed to 0.15 to allow valid synonyms like "Stroke" → "Cerebrovascular Accident"
        if similarity < 0.15 and len(span) > 3:
            abbrevs = {"mri", "ct", "mi", "copd", "hiv", "aids", "gbm", "avm", "pet", "eeg"}
            if span.lower() not in abbrevs:
                logger.warning(f"Low similarity: '{span}' → '{canonical_name}' ({similarity:.2f})")
                return False
        return True
    
    def canonicalize(self, span: str, sentence: str) -> Dict[str, Any]:
        """
        Canonicalize with LLM. Returns sentinel for negations, falls back to heuristic on errors.
        
        Returns:
            {"canonical_name": str, "semantic_category": str, "confidence": float}
            
            Special case - negation detected:
            {"canonical_name": "NEGATED", "semantic_category": "NONE", "confidence": 0.0}
        """
        span = (span or "").strip()
        sentence = (sentence or "").strip()
        
        # Empty span → heuristic
        if not span:
            return _heuristic_canonicalize(span, sentence)
        
        # Check API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            try:
                from utils.runtime import get_config
                api_key = get_config("providers.openai_api_key")
            except:
                pass
        
        if not api_key:
            logger.debug("No API key, using heuristic")
            return _heuristic_canonicalize(span, sentence)
        
        # Try LLM
        try:
            result = self._call_openai_canonicalize(span, sentence, timeout_s=30.0)
            
            # FIXED: Return sentinel directly (do NOT fallback to heuristic)
            # This prevents "no tumor" from becoming a positive "tumor" entity
            if result.get("canonical_name") == "NEGATED" or result.get("semantic_category") == "NONE":
                logger.info(f"Negation detected: '{span}' → skipping entity")
                return {"canonical_name": "NEGATED", "semantic_category": "NONE", "confidence": 0.0}
            
            # Validate
            if not self._validate_canonicalization(span, result["canonical_name"]):
                logger.warning(f"Validation failed: '{span}' → using heuristic")
                return _heuristic_canonicalize(span, sentence)
            
            # Check confidence threshold
            if result["confidence"] < 0.5:
                logger.warning(f"Low confidence ({result['confidence']:.2f}): '{span}' → using heuristic")
                return _heuristic_canonicalize(span, sentence)
            
            logger.info(f"✓ '{span}' → '{result['canonical_name']}' ({result['semantic_category']}, {result['confidence']:.2f})")
            return result
            
        except TimeoutError as e:
            logger.warning(f"Timeout: {e} → using heuristic")
        except ValueError as e:
            logger.error(f"Validation error: {e} → using heuristic")
        except Exception as e:
            logger.error(f"Unexpected error: {e} → using heuristic")
        
        return _heuristic_canonicalize(span, sentence)

