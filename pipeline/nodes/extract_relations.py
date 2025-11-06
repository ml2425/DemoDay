"""Node 2: Extract relations using LLM with evidence snippets."""

import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
from pipeline.relations.schema_loader import RelationSchema

load_dotenv()


def build_relation_extraction_prompt(full_text: str, schema: RelationSchema) -> str:
    """Build prompt for relation extraction with 2-4 sentence evidence snippets."""
    
    relations_list = "\n".join([
        f"- {rel_id}: {rel_data['description']}"
        for rel_id, rel_data in schema.relations.items()
    ])
    
    return f"""Extract medical relationships from this text and return exact evidence snippets.

**Full Text:**
"{full_text}"

**Allowed Relation Types (Schema):**
{relations_list}

**Task:**
For each relationship found:
1. Extract triple: (head_entity, relation_type, tail_entity)
2. Copy EXACT 2-4 sentence snippet where relationship appears
3. Provide location (paragraph, sentence numbers, character positions)

**CRITICAL - Evidence Snippet Rules:**
- Include 2-4 COMPLETE sentences containing the relationship
- Start from sentence introducing the relationship
- Include enough context to make relationship clear
- Copy text EXACTLY (no modifications, no paraphrasing)
- If relationship spans multiple sentences, include ALL of them

**Output JSON Array:**
[
  {{
    "head": "Temozolomide",
    "relation": "TREATS",
    "tail": "Glioblastoma",
    "evidence_snippet": "The standard treatment protocol involves temozolomide chemotherapy combined with radiotherapy. This combination therapy has been shown to improve patient survival rates. Studies demonstrate a median survival of 14.6 months with this approach.",
    "location": {{
      "paragraph": 2,
      "sentence_start": 3,
      "sentence_end": 5,
      "char_start": 450,
      "char_end": 620
    }},
    "confidence": 0.95
  }}
]

Return empty array [] if no valid relationships found.
"""


def extract_relations_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relations using LLM with evidence snippets.
    
    Expected state keys:
        - full_text: Source text
        - source_id: Source identifier
    
    Updates state with:
        - extracted_relations: List of relation dicts
    """
    full_text = state.get("full_text", "")
    if not full_text:
        raise ValueError("full_text is required")
    
    # Load schema
    schema = RelationSchema()
    
    # Build prompt
    prompt = build_relation_extraction_prompt(full_text, schema)
    
    # Call OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical knowledge extraction expert. Extract relationships with exact evidence snippets."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON (handle both array and object formats)
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            relations = json.loads(content)
            if isinstance(relations, dict) and "relations" in relations:
                relations = relations["relations"]
            if not isinstance(relations, list):
                relations = [relations] if relations else []
        except json.JSONDecodeError:
            print(f"[WARN] Failed to parse LLM response as JSON: {content[:200]}")
            relations = []
        
        # Validate relations against schema
        allowed_relations = schema.get_allowed_relations()
        validated = []
        
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            
            rel_id = rel.get("relation", "")
            if rel_id not in allowed_relations:
                continue
            
            # Normalize entities using schema
            head = schema.normalize_entity(rel.get("head", ""))
            tail = schema.normalize_entity(rel.get("tail", ""))
            
            validated.append({
                "head": head,
                "relation": rel_id,
                "tail": tail,
                "relation_raw": rel.get("relation", ""),  # Keep original for research
                "evidence_snippet": rel.get("evidence_snippet", ""),
                "location": rel.get("location", {}),
                "confidence": rel.get("confidence", 0.75)
            })
        
        state["extracted_relations"] = validated
        print(f"[OK] Extracted {len(validated)} relations from text")
        
    except Exception as e:
        print(f"[ERROR] Relation extraction failed: {e}")
        state["extracted_relations"] = []
    
    return state

