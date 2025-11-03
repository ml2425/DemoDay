"""
Provenance logging utilities.
Handles prompt hashing and upserting to prompts table.
"""

import hashlib
import sqlite3


def prompt_sha(content: str) -> str:
    """
    Compute SHA256 hash of prompt content.
    
    Args:
        content: Prompt content text
        
    Returns:
        SHA256 hex digest
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def upsert_prompt(conn: sqlite3.Connection, role: str, content: str) -> int:
    """
    Upsert a prompt into the prompts table (insert if sha256 not present).
    
    Uses sha256 as unique identifier - if prompt with same content exists,
    returns existing prompt_id; otherwise inserts new prompt.
    
    Args:
        conn: Database connection
        role: Prompt role (e.g., "system", "user", "assistant")
        content: Prompt content text
        
    Returns:
        prompt_id of the prompt (existing or newly inserted)
    """
    sha256 = prompt_sha(content)
    
    # Check if prompt exists
    cursor = conn.execute(
        "SELECT prompt_id FROM prompts WHERE sha256 = ?",
        (sha256,)
    )
    row = cursor.fetchone()
    
    if row:
        # Return existing prompt_id
        return row[0]
    else:
        # Insert new prompt
        cursor = conn.execute(
            """
            INSERT INTO prompts (role, content, sha256)
            VALUES (?, ?, ?)
            """,
            (role, content, sha256)
        )
        conn.commit()
        return cursor.lastrowid

