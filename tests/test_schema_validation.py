"""
Test schema validation using configs/schema.yaml domain/range rules.
"""

import pytest
from pipeline.validators import load_schema, validate_entity_type, validate_relation_domain_range


def test_load_schema():
    """Test that schema.yaml can be loaded."""
    schema = load_schema()
    assert "entity_types" in schema
    assert "relations" in schema


def test_validate_entity_types():
    """Test entity type validation."""
    schema = load_schema()
    valid_types = schema.get("entity_types", [])
    
    for entity_type in valid_types:
        assert validate_entity_type(entity_type, schema) is True
    
    # Invalid type should return False
    assert validate_entity_type("INVALID_TYPE", schema) is False


def test_validate_relation_domain_range():
    """Test relation domain/range validation using schema.yaml rules."""
    schema = load_schema()
    
    # Test CAUSES relation (domain: MICROBE/DISORDER/DRUG, range: DISORDER/FINDING)
    assert validate_relation_domain_range("CAUSES", "MICROBE", "DISORDER", schema) is True
    assert validate_relation_domain_range("CAUSES", "MICROBE", "FINDING", schema) is True
    assert validate_relation_domain_range("CAUSES", "MICROBE", "DRUG", schema) is False  # Invalid range
    
    # Test TREATS relation (domain: DRUG/PROCEDURE, range: DISORDER)
    assert validate_relation_domain_range("TREATS", "DRUG", "DISORDER", schema) is True
    assert validate_relation_domain_range("TREATS", "PROCEDURE", "DISORDER", schema) is True
    assert validate_relation_domain_range("TREATS", "DRUG", "FINDING", schema) is False  # Invalid range
    
    # Test disabled relation should return False
    assert validate_relation_domain_range("SENSITIVE_TO", "MICROBE", "DRUG", schema) is False  # Disabled


def test_invalid_relation_id():
    """Test that invalid relation IDs return False."""
    schema = load_schema()
    assert validate_relation_domain_range("INVALID_REL", "DISORDER", "FINDING", schema) is False

