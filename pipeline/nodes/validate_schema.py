"""Node 3: Validate relations against schema and normalize."""

from typing import Dict, Any
from pipeline.relations.schema_loader import RelationSchema


def validate_schema_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate relations against schema and normalize entities.
    
    Expected state keys:
        - extracted_relations: List of relation dicts
    
    Updates state with:
        - validated_relations: List of validated relation dicts
    """
    extracted = state.get("extracted_relations", [])
    schema = RelationSchema()
    
    validated = []
    allowed_relations = schema.get_allowed_relations()
    
    for rel in extracted:
        rel_id = rel.get("relation", "")
        
        # Check relation exists in schema
        if rel_id not in allowed_relations:
            continue
        
        # Get relation info for domain/range validation (if needed)
        rel_info = schema.get_relation_info(rel_id)
        if not rel_info:
            continue
        
        # Normalize entities (already done in extract_relations, but double-check)
        head = schema.normalize_entity(rel.get("head", ""))
        tail = schema.normalize_entity(rel.get("tail", ""))
        
        validated.append({
            "head": head,
            "relation": rel_id,
            "tail": tail,
            "relation_raw": rel.get("relation_raw", rel_id),
            "evidence_snippet": rel.get("evidence_snippet", ""),
            "location": rel.get("location", {}),
            "confidence": rel.get("confidence", 0.75)
        })
    
    state["validated_relations"] = validated
    print(f"[OK] Validated {len(validated)} relations")
    
    return state

