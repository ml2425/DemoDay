"""Schema loader for relation schemas."""

import yaml
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).parent.parent.parent


class RelationSchema:
    """Loads and manages relation schemas from YAML files."""
    
    def __init__(self, schema_file: str = "neurosurgery.yaml"):
        """
        Initialize schema loader.
        
        Args:
            schema_file: Name of schema file in configs/relations/
        """
        self.schema_file = schema_file
        self.schema_path = ROOT / "configs" / "relations" / schema_file
        self.schema_data = self._load_schema()
        self.relations = self._extract_relations()
        self.alias_map = self._build_alias_map()
    
    def _load_schema(self) -> dict:
        """Load schema from YAML file."""
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def _extract_relations(self) -> Dict[str, dict]:
        """Extract all relations (core + extended + optional) into a flat dict."""
        relations = {}
        
        # Core relations
        core = self.schema_data.get("core_relations", {})
        for rel_id, rel_data in core.items():
            if rel_data.get("enabled", True):
                relations[rel_id] = {
                    "id": rel_id,
                    "description": rel_data.get("description", ""),
                    "domain": rel_data.get("domain", []),
                    "range": rel_data.get("range", []),
                    "priority": rel_data.get("priority", 2),
                    "examples": rel_data.get("examples", [])
                }
        
        # Extended relations
        extended = self.schema_data.get("extended_relations", {})
        for rel_id, rel_data in extended.items():
            if rel_data.get("enabled", True):
                relations[rel_id] = {
                    "id": rel_id,
                    "description": rel_data.get("description", ""),
                    "domain": rel_data.get("domain", []),
                    "range": rel_data.get("range", []),
                    "priority": rel_data.get("priority", 2),
                    "examples": rel_data.get("examples", [])
                }
        
        # Optional relations
        optional = self.schema_data.get("optional_relations", {})
        for rel_id, rel_data in optional.items():
            if rel_data.get("enabled", True):
                relations[rel_id] = {
                    "id": rel_id,
                    "description": rel_data.get("description", ""),
                    "domain": rel_data.get("domain", []),
                    "range": rel_data.get("range", []),
                    "priority": rel_data.get("priority", 3),
                    "examples": rel_data.get("examples", [])
                }
        
        return relations
    
    def _build_alias_map(self) -> Dict[str, str]:
        """
        Build alias map from schema examples and synonyms.
        Maps aliases to canonical names (lowercase, normalized).
        """
        alias_map = {}
        
        # Extract from examples
        for rel_id, rel_data in self.relations.items():
            examples = rel_data.get("examples", [])
            for example in examples:
                head = example.get("head", "")
                tail = example.get("tail", "")
                
                # Normalize and add to map
                head_canonical = self._normalize_entity(head)
                tail_canonical = self._normalize_entity(tail)
                
                alias_map[head.lower()] = head_canonical
                alias_map[tail.lower()] = tail_canonical
        
        return alias_map
    
    @staticmethod
    def _normalize_entity(entity: str) -> str:
        """
        Normalize entity: lowercase, strip punctuation, collapse whitespace.
        
        Args:
            entity: Entity string
            
        Returns:
            Normalized entity string
        """
        import re
        # Lowercase
        normalized = entity.lower()
        # Strip punctuation (keep alphanumeric and spaces)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def get_allowed_relations(self) -> List[str]:
        """Get list of allowed relation IDs."""
        return list(self.relations.keys())
    
    def get_relation_info(self, rel_id: str) -> Optional[dict]:
        """Get relation info by ID."""
        return self.relations.get(rel_id)
    
    def normalize_entity(self, entity: str) -> str:
        """
        Normalize entity using alias map if available.
        
        Args:
            entity: Entity string
            
        Returns:
            Normalized canonical entity
        """
        normalized = self._normalize_entity(entity)
        
        # Check alias map
        entity_lower = entity.lower()
        if entity_lower in self.alias_map:
            return self.alias_map[entity_lower]
        
        return normalized

