"""
Schema validation module.
Validates entity types, relations, and domain/range constraints.
"""

from typing import Dict, Any, List, Optional
import yaml


def load_schema(config_path: str = "configs/schema.yaml") -> Dict[str, Any]:
    """
    Load schema validation rules from YAML file.
    
    Args:
        config_path: Path to schema.yaml
        
    Returns:
        Schema dictionary with entity_types, relations, etc.
    """
    # Stub: return minimal structure
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "entity_types": [],
            "relations": [],
            "mcq_validation": {}
        }


def validate_entity_type(entity_type: str, schema: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate that an entity type is in the allowed list.
    
    Args:
        entity_type: Entity type to validate
        schema: Optional schema dict (loads if None)
        
    Returns:
        True if valid, False otherwise
    """
    if schema is None:
        schema = load_schema()
    return entity_type in schema.get("entity_types", [])


def validate_relation_domain_range(
    relation_id: str,
    head_type: str,
    tail_type: str,
    schema: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Validate that a relation's domain and range match entity types.
    
    Args:
        relation_id: Relation ID
        head_type: Head entity semantic category
        tail_type: Tail entity semantic category
        schema: Optional schema dict
        
    Returns:
        True if valid, False otherwise
    """
    if schema is None:
        schema = load_schema()
    
    relations = schema.get("relations", [])
    for rel in relations:
        if rel.get("id") == relation_id and rel.get("enabled", False):
            return (
                head_type in rel.get("domain", []) and
                tail_type in rel.get("range", [])
            )
    return False

