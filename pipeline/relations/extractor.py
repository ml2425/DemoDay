"""
LLM-based relation extraction with domain-specific schema constraints.
Replaces regex-based extraction for better semantic understanding.
"""

import os
import json
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from .schema_loader import RelationSchema
from utils.cache import hash_key, cache_get, cache_set

logger = logging.getLogger(__name__)

# Import OpenAI
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def extract_relations_llm_with_schema(
    sentence: str,
    entities: List[Dict],
    domain: str = "neurosurgery",
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict]:
    """
    Extract relations using LLM with domain-specific schema constraints.
    
    Args:
        sentence: Sentence text containing entities
        entities: List of entity dicts with keys: entity_id, name, type, span_text
        domain: Medical domain (default: "neurosurgery")
        conn: Optional database connection for caching
        
    Returns:
        List of relation dicts with keys: head, relation, tail, confidence, evidence
    """
    # Validate inputs
    if not sentence or not entities:
        return []
    
    # Build cache key (sentence + sorted entity names + domain)
    # Sort entity names for consistent cache key
    entity_names = sorted([e.get("name", "") for e in entities])
    cache_key = f"rel_extract|{hash_key(sentence, '|'.join(entity_names), domain)}"
    
    # Check cache first (if connection provided)
    if conn:
        cached_value = cache_get(conn, cache_key)
        if cached_value:
            logger.debug(f"Cache hit for relation extraction: {sentence[:50]}...")
            return json.loads(cached_value)
    
    # Log start of LLM call (for progress visibility)
    logger.info(f"Extracting relations from sentence: {sentence[:60]}...")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            from utils.runtime import get_config
            api_key = get_config("providers.openai_api_key")
        except:
            pass
    
    if not api_key:
        logger.warning("No OpenAI API key, skipping LLM relation extraction")
        return []
    
    if OpenAI is None:
        logger.error("openai package not installed")
        return []
    
    # Load schema
    schema_loader = RelationSchema()
    schema = schema_loader.load_schema(domain)
    
    # Get allowed relations (priority <= 2 by default)
    allowed_relations = schema_loader.get_allowed_relations(domain, priority_threshold=2)
    if not allowed_relations:
        logger.warning(f"No enabled relations found for domain: {domain}")
        return []
    
    # Build prompt with schema-defined relations
    relations_section = schema_loader.build_llm_prompt_section(domain)
    
    # Format entities for prompt
    entities_str = "\n".join([
        f"- {e['name']} (Type: {e['type']})"
        for e in entities
    ])
    
    # Get prompt config
    prompt_config = schema.get("prompt_config", {})
    max_relations = prompt_config.get("max_relations_per_sentence", 5)
    temperature = prompt_config.get("temperature", 0)
    model = prompt_config.get("model", "gpt-4o-mini")
    
    # Build prompt
    prompt = f"""Extract medical relationships from this sentence.

**Medical Domain:** {domain.upper()}

**Sentence:**
"{sentence}"

**Entities in sentence:**
{entities_str}

{relations_section}

**Extraction rules:**
1. Use ONLY the relation types listed above (exact spelling)
2. Both entities must be semantically present in sentence (accounting for abbreviations/synonyms)
3. Relationship must be clearly supported by sentence content
4. Output top {max_relations} most confident relationships
5. If no relation type fits, return empty array

**Output valid JSON array:**
[
  {{
    "head": "entity name from list",
    "relation": "EXACT_RELATION_FROM_LIST",
    "tail": "entity name from list",
    "confidence": 0.0-1.0,
    "evidence": "key phrase from sentence"
  }}
]

Return [] if no valid relationships found.
"""
    
    # Call LLM
    try:
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": "You are a medical relationship extraction system. Output only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            # Remove response_format constraint - prompt asks for array, not object
            # response_format={"type": "json_object"},  # REMOVED - allows LLM to return array directly
            timeout=30.0
        )
        
        content = response.choices[0].message.content if response and response.choices else ""
        
        # Parse JSON response
        try:
            # Handle both array and object with array
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                relationships = parsed.get("relationships", parsed.get("relations", []))
            else:
                relationships = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response content: {content[:200]}")
            return []
        
        # Validate each extracted relation against schema
        validated = []
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            
            rel_type = rel.get("relation", "")
            head_name = rel.get("head", "")
            tail_name = rel.get("tail", "")
            
            # Check relation type is allowed
            if rel_type not in allowed_relations:
                logger.debug(f"LLM returned disallowed relation: {rel_type}")
                continue
            
            # Find entities by name
            head_entity = next((e for e in entities if e["name"] == head_name), None)
            tail_entity = next((e for e in entities if e["name"] == tail_name), None)
            
            if not head_entity or not tail_entity:
                logger.debug(f"Entity not found in sentence: {head_name} or {tail_name}")
                continue
            
            # Validate domain/range constraints
            is_valid = schema_loader.validate_relation(
                domain,
                head_entity["type"],
                rel_type,
                tail_entity["type"]
            )
            
            if not is_valid:
                logger.debug(f"Relation failed schema validation: {rel}")
                continue
            
            # Validate confidence
            confidence = float(rel.get("confidence", 0.0))
            min_conf = prompt_config.get("min_confidence_threshold", 0.7)
            if confidence < min_conf:
                logger.debug(f"Low confidence ({confidence:.2f} < {min_conf}): {rel}")
                continue
            
            validated.append({
                "head": head_name,
                "relation": rel_type,
                "tail": tail_name,
                "confidence": confidence,
                "evidence": rel.get("evidence", sentence[:100])
            })
        
        # Return top N by confidence
        validated.sort(key=lambda x: x["confidence"], reverse=True)
        result = validated[:max_relations]
        
        # Cache result (if connection provided)
        if conn:
            cache_set(conn, cache_key, json.dumps(result), cache_type="relation_extraction")
        
        return result
        
    except Exception as e:
        logger.error(f"LLM relation extraction failed: {e}")
        return []
