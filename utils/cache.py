"""
Cache utilities for SQLite cache table.
Provides key hashing and cache get/set operations.
"""

import hashlib
import re
import json
import sqlite3
from typing import Optional


def normalize_text(text: str) -> str:
    """
    Normalize text for cache key generation.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text (lowercase, whitespace collapsed)
    """
    # Remove citation markers like [1] or [1-3]
    text = re.sub(r'\[\d+(?:-\d+)?\]', '', text)
    # Lowercase and collapse whitespace
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def hash_key(*parts: str) -> str:
    """
    Generate cache key from normalized parts.
    
    Args:
        *parts: Variable number of string parts to hash
        
    Returns:
        SHA256 hex digest of joined normalized strings
    """
    normalized_parts = [normalize_text(str(part)) for part in parts]
    combined = "|".join(normalized_parts)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def cache_get(conn: sqlite3.Connection, key: str) -> Optional[str]:
    """
    Get cached value by key.
    
    Args:
        conn: Database connection
        key: Cache key
        
    Returns:
        Cached JSON string or None if not found
    """
    cursor = conn.execute(
        "SELECT cache_value FROM cache WHERE cache_key = ?",
        (key,)
    )
    row = cursor.fetchone()
    
    if row:
        # Update hit count
        conn.execute(
            "UPDATE cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
            (key,)
        )
        conn.commit()
        return row[0]
    
    return None


def cache_set(conn: sqlite3.Connection, key: str, value_json: str, cache_type: str = "canonicalization") -> None:
    """
    Set cached value in cache table.
    
    Args:
        conn: Database connection
        key: Cache key
        value_json: JSON string value to cache
        cache_type: Type of cache entry (default: "canonicalization")
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO cache (cache_key, cache_value, cache_type, hit_count)
        VALUES (?, ?, ?, 0)
        """,
        (key, value_json, cache_type)
    )
    conn.commit()

