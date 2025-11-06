"""
Relation verification module.
LLM validates that evidence supports extracted triples.
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, Tuple, Optional

from providers.llm_adapter import LLMAdapter
from utils.cache import hash_key, cache_get, cache_set

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Relation definitions for prompt context
RELATION_DEFINITIONS = {
    "TREATS": "therapeutic intervention for a condition",
    "HAS_FINDING": "patient exhibits clinical sign or symptom", 
    "INVESTIGATED_BY": "diagnostic test or procedure used to assess condition",
    "CAUSES": "etiological agent produces pathological condition",
    "CONTRAINDICATES": "condition prohibits use of intervention",
    "SENSITIVE_TO": "microbe susceptible to antimicrobial agent",
    "RESISTANT_TO": "microbe not susceptible to antimicrobial agent"
}


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
        # Get verifier model from config
        try:
            from utils.runtime import get_config
            self.verifier_model = get_config("llm.verifier_model", "gpt-4o-mini")
        except:
            self.verifier_model = "gpt-4o-mini"
    
    def _llm_verify(self, sentence: str, triple: Tuple[str, str, str]) -> Dict[str, Any]:
        """
        Use LLM to verify if sentence semantically entails the relationship.
        Handles abbreviations, synonyms, and paraphrasing naturally.
        
        Args:
            sentence: Original sentence text from document
            triple: (head_canonical_name, relation_id, tail_canonical_name)
            
        Returns:
            {"entailed": bool, "confidence": float, "reasoning": str}
        """
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        
        head_name, rel_id, tail_name = triple
        rel_description = RELATION_DEFINITIONS.get(rel_id, rel_id)
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            try:
                from utils.runtime import get_config
                api_key = get_config("providers.openai_api_key")
            except:
                pass
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found")
        
        # Build prompt
        prompt = f"""Verify if this medical sentence supports the claimed relationship.

**Sentence from medical literature:**
"{sentence}"

**Claimed relationship:**
- Head entity: {head_name}
- Relationship: {rel_id} ({rel_description})
- Tail entity: {tail_name}

**Verification rules:**
1. The sentence may use abbreviations (e.g., "MRI" for "Magnetic Resonance Imaging", "TMZ" for "Temozolomide")
2. The sentence may use synonyms (e.g., "heart attack" for "Myocardial Infarction")
3. The relationship may be stated implicitly or explicitly
4. Entity names must semantically match terms in the sentence (accounting for abbreviations/synonyms)
5. The relationship must be supported by the sentence content

**Examples of valid entailment:**
- Sentence: "MRI showed tumor" → (Magnetic Resonance Imaging, INVESTIGATED_BY, Brain Neoplasm) = TRUE
- Sentence: "treated with TMZ" → (Temozolomide, TREATS, Glioblastoma) = TRUE  
- Sentence: "patient has headache" → (Patient, HAS_FINDING, Headache) = TRUE
- Sentence: "cultures grew S. aureus" → (Staphylococcus aureus, CAUSES, Infection) = TRUE

**Examples of invalid entailment:**
- Sentence: "MRI was performed" → (Magnetic Resonance Imaging, TREATS, Glioma) = FALSE (wrong relationship)
- Sentence: "history of diabetes" → (Insulin, TREATS, Hypertension) = FALSE (entities not mentioned)
- Sentence: "no evidence of tumor" → (Brain, HAS_FINDING, Neoplasm) = FALSE (negated)

**Output valid JSON only:**
{{"entailed": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

**Confidence scoring:**
- High (0.85-1.0): Entities clearly present (accounting for abbreviations), relationship explicitly stated
- Medium (0.6-0.84): Entities present, relationship implied or requires inference
- Low (0.0-0.59): Uncertain entity matching or weak relationship support

Return entailed=true only if the sentence genuinely supports this specific relationship between these entities.
"""
        
        try:
            client = OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=self.verifier_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a medical relation verification system. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                timeout=30.0
            )
            
            content = response.choices[0].message.content if response and response.choices else ""
            
            # Parse JSON
            result = json.loads(content)
            
            entailed = bool(result.get("entailed", False))
            confidence = float(result.get("confidence", 0.0))
            reasoning = str(result.get("reasoning", ""))
            
            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))
            
            return {
                "entailed": entailed,
                "confidence": confidence,
                "reasoning": reasoning
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in LLM verification: {e}")
            raise ValueError(f"Invalid JSON from LLM: {content[:200]}")
        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            raise RuntimeError(f"LLM verification error: {e}")
    
    def verify(self, sentence: str, triple: Tuple[str, str, str]) -> Dict[str, Any]:
        """
        Verify if sentence supports the relationship using LLM.
        
        Args:
            sentence: Original sentence text from document
            triple: (head_canonical_name, relation_id, tail_canonical_name)
            
        Returns:
            {
                "entailed": bool,      # True if relationship supported
                "confidence": float,   # 0.0-1.0
                "reasoning": str       # Explanation
            }
        
        Note: Works with canonical names. No span_text needed.
              LLM understands abbreviations and synonyms naturally.
        """
        head_name, rel_id, tail_name = triple
        
        # Build cache key using existing hash_key function
        cache_key = f"verify|{hash_key(sentence, head_name, rel_id, tail_name)}"
        
        # Check cache first (using existing pattern)
        cached_value = cache_get(self.conn, cache_key)
        if cached_value:
            logger.debug(f"Cache hit for triple: {triple}")
            return json.loads(cached_value)
        
        # Perform LLM verification
        try:
            result = self._llm_verify(sentence, triple)
            
            # Cache result (using existing pattern)
            cache_set(self.conn, cache_key, json.dumps(result), cache_type="verification")
            
            # Log result
            status = "VERIFIED" if result["entailed"] else "REJECTED"
            logger.info(
                f"{status}: ({head_name}, {rel_id}, {tail_name}) "
                f"[conf={result['confidence']:.2f}] - {result['reasoning']}"
            )
            
            return result
            
        except Exception as e:
            # On error, return rejection with low confidence
            logger.error(f"Verification failed for {triple}: {e}")
            return {
                "entailed": False,
                "confidence": 0.0,
                "reasoning": f"Verification error: {str(e)}"
            }

