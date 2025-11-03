"""
Pytest configuration and fixtures.
"""

import pytest
import sqlite3
import os
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database file path."""
    db_file = tmp_path / "test.db"
    return str(db_file)


@pytest.fixture
def db_connection(db_path):
    """
    Create an in-memory SQLite database from schema.sql with foreign keys enabled.
    """
    # Read schema.sql
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Execute schema
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
    
    yield conn
    
    conn.close()


@pytest.fixture
def sample_doc_id(db_connection):
    """Insert a sample document and return its ID."""
    cursor = db_connection.execute(
        "INSERT INTO docs (source_kind, sha256) VALUES (?, ?)",
        ("LOCAL_PDF", "test_sha256_hash")
    )
    doc_id = cursor.lastrowid
    db_connection.commit()
    return doc_id

