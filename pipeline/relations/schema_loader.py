import yaml
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class RelationSchema:
    """Load and manage relation schemas for different medical domains"""
    
    def __init__(self, schema_dir: str = "configs/relations"):
        self.schema_dir = Path(schema_dir)
        self.schemas = {}
        self.base_schema = None
        
    def load_schema(self, domain: str) -> Dict:
        """Load relation schema for a specific domain"""
        if domain in self.schemas:
            return self.schemas[domain]
        
        schema_file = self.schema_dir / f"{domain}.yaml"
        
        if not schema_file.exists():
            logger.warning(f"Schema not found: {schema_file}, using base schema")
            return self.load_base_schema()
        
        with open(schema_file, 'r') as f:
            schema = yaml.safe_load(f)
        
        # Merge with base schema if it exists
        if self.base_schema is None:
            self.base_schema = self.load_base_schema()
        
        merged_schema = self._merge_schemas(self.base_schema, schema)
        self.schemas[domain] = merged_schema
        
        logger.info(f"Loaded {domain} schema with {len(merged_schema['relations'])} relations")
        return merged_schema
    
    def load_base_schema(self) -> Dict:
        """Load common base relations"""
        base_file = self.schema_dir / "_base.yml"
        
        if not base_file.exists():
            logger.warning("No base schema found, using empty schema")
            return {"relations": {}, "metadata": {}}
        
        with open(base_file, 'r') as f:
            return yaml.safe_load(f)
    
    def _merge_schemas(self, base: Dict, domain: Dict) -> Dict:
        """Merge base and domain-specific schemas"""
        merged = {"metadata": domain.get("metadata", {}), "relations": {}}
        
        # Add base relations
        if "common_relations" in base:
            merged["relations"].update(base["common_relations"])
        
        # Add domain-specific relations (override if conflicts)
        for section in ["core_relations", "extended_relations", "optional_relations"]:
            if section in domain:
                merged["relations"].update(domain[section])
        
        # Add validation and prompt config
        merged["validation"] = domain.get("validation", {})
        merged["prompt_config"] = domain.get("prompt_config", {})
        
        return merged
    
    def get_allowed_relations(self, domain: str, priority_threshold: int = 2) -> List[str]:
        """Get list of enabled relation types for a domain"""
        schema = self.load_schema(domain)
        
        allowed = []
        for rel_name, rel_config in schema["relations"].items():
            if rel_config.get("enabled", True):
                priority = rel_config.get("priority", 3)
                if priority <= priority_threshold:
                    allowed.append(rel_name)
        
        return allowed
    
    def get_relation_config(self, domain: str, relation_type: str) -> Optional[Dict]:
        """Get configuration for a specific relation"""
        schema = self.load_schema(domain)
        return schema["relations"].get(relation_type)
    
    def validate_relation(
        self, 
        domain: str,
        head_type: str,
        relation_type: str,
        tail_type: str
    ) -> bool:
        """Validate if relation follows domain/range constraints"""
        rel_config = self.get_relation_config(domain, relation_type)
        
        if not rel_config:
            logger.warning(f"Unknown relation type: {relation_type}")
            return False
        
        if not rel_config.get("enabled", True):
            logger.debug(f"Relation disabled: {relation_type}")
            return False
        
        # Check domain constraint
        domain_types = rel_config.get("domain", [])
        if domain_types and head_type not in domain_types:
            logger.debug(
                f"Domain mismatch: {head_type} not in {domain_types} "
                f"for relation {relation_type}"
            )
            return False
        
        # Check range constraint
        range_types = rel_config.get("range", [])
        if range_types and tail_type not in range_types:
            logger.debug(
                f"Range mismatch: {tail_type} not in {range_types} "
                f"for relation {relation_type}"
            )
            return False
        
        return True
    
    def get_prompt_examples(self, domain: str, relation_type: str) -> List[Dict]:
        """Get examples for prompting LLM"""
        rel_config = self.get_relation_config(domain, relation_type)
        
        if not rel_config:
            return []
        
        return rel_config.get("examples", [])
    
    def build_llm_prompt_section(self, domain: str) -> str:
        """Build relation definitions section for LLM prompt"""
        schema = self.load_schema(domain)
        allowed = self.get_allowed_relations(domain)
        
        prompt_lines = ["**ALLOWED RELATION TYPES (use exactly these):**\n"]
        
        for rel_name in allowed:
            rel_config = schema["relations"][rel_name]
            desc = rel_config.get("description", "")
            domain_types = rel_config.get("domain", [])
            range_types = rel_config.get("range", [])
            
            prompt_lines.append(f"- {rel_name}: {desc}")
            prompt_lines.append(f"  Domain: {', '.join(domain_types)}")
            prompt_lines.append(f"  Range: {', '.join(range_types)}")
            
            # Optionally include examples
            examples = rel_config.get("examples", [])
            if examples and schema.get("prompt_config", {}).get("include_examples_in_prompt", False):
                ex = examples[0]  # Use first example
                prompt_lines.append(
                    f"  Example: \"{ex['sentence']}\" "
                    f"→ ({ex['head']}, {rel_name}, {ex['tail']})"
                )
            
            prompt_lines.append("")
        
        return "\n".join(prompt_lines)