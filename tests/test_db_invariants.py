"""
Test database invariants and referential integrity.
"""

import pytest


def test_no_orphan_triples(db_connection):
    """
    Assert that no orphan triples exist (all triples must reference valid entities).
    This will pass with an empty database.
    """
    cursor = db_connection.execute("""
        SELECT COUNT(*) 
        FROM triples t
        WHERE NOT EXISTS (
            SELECT 1 FROM entities e1 WHERE e1.entity_id = t.head_entity
        )
        OR NOT EXISTS (
            SELECT 1 FROM entities e2 WHERE e2.entity_id = t.tail_entity
        )
    """)
    
    orphan_count = cursor.fetchone()[0]
    assert orphan_count == 0, f"Found {orphan_count} orphan triples"


def test_no_orphan_evidence(db_connection):
    """
    Assert that all evidence rows reference valid triples.
    """
    cursor = db_connection.execute("""
        SELECT COUNT(*) 
        FROM evidence e
        WHERE NOT EXISTS (
            SELECT 1 FROM triples t WHERE t.triple_id = e.triple_id
        )
    """)
    
    orphan_count = cursor.fetchone()[0]
    assert orphan_count == 0, f"Found {orphan_count} orphan evidence rows"


def test_no_orphan_entities(db_connection):
    """
    Assert that all entities reference valid concepts and docs.
    """
    cursor = db_connection.execute("""
        SELECT COUNT(*) 
        FROM entities e
        WHERE (e.canonical_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM concepts c WHERE c.canonical_id = e.canonical_id
        ))
        OR NOT EXISTS (
            SELECT 1 FROM docs d WHERE d.doc_id = e.doc_id
        )
    """)
    
    orphan_count = cursor.fetchone()[0]
    assert orphan_count == 0, f"Found {orphan_count} orphan entities"

