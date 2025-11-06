#!/usr/bin/env python3
"""
Reporting and summary generation for the knowledge graph.
Provides counts, provenance metrics, and per-document summaries.
"""

import sys
import sqlite3
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_utils import connect


def open_conn(db_path: str = "database/kg.sqlite") -> sqlite3.Connection:
    """
    Open database connection.
    
    Args:
        db_path: Path to database file
        
    Returns:
        Database connection
    """
    return connect(db_path)


def overall_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Get overall counts for all main tables.
    
    Args:
        conn: Database connection
        
    Returns:
        Dict with keys: docs, concepts, entities, relations, triples, evidence, mcqs
    """
    counts = {}
    
    # Count docs
    cursor = conn.execute("SELECT COUNT(*) FROM docs")
    counts["docs"] = cursor.fetchone()[0]
    
    # Count concepts
    cursor = conn.execute("SELECT COUNT(*) FROM concepts")
    counts["concepts"] = cursor.fetchone()[0]
    
    # Count entities
    cursor = conn.execute("SELECT COUNT(*) FROM entities")
    counts["entities"] = cursor.fetchone()[0]
    
    # Count relations
    cursor = conn.execute("SELECT COUNT(*) FROM relations")
    counts["relations"] = cursor.fetchone()[0]
    
    # Count triples
    cursor = conn.execute("SELECT COUNT(*) FROM triples")
    counts["triples"] = cursor.fetchone()[0]
    
    # Count evidence
    cursor = conn.execute("SELECT COUNT(*) FROM evidence")
    counts["evidence"] = cursor.fetchone()[0]
    
    # Count MCQs
    cursor = conn.execute("SELECT COUNT(*) FROM mcqs")
    counts["mcqs"] = cursor.fetchone()[0]
    
    return counts


def provenance_metrics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculate provenance completeness metrics.
    
    Args:
        conn: Database connection
        
    Returns:
        Dict with keys:
        - triples_with_evidence (int)
        - triples_total (int)
        - provenance_completeness (float 0..1)
        - avg_triple_confidence (float or None)
    """
    metrics = {}
    
    # Count total triples
    cursor = conn.execute("SELECT COUNT(*) FROM triples")
    triples_total = cursor.fetchone()[0]
    metrics["triples_total"] = triples_total
    
    # Count triples with evidence
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT t.triple_id)
        FROM triples t
        INNER JOIN evidence e ON t.triple_id = e.triple_id
    """)
    triples_with_evidence = cursor.fetchone()[0]
    metrics["triples_with_evidence"] = triples_with_evidence
    
    # Calculate completeness (0 if no triples)
    if triples_total > 0:
        metrics["provenance_completeness"] = triples_with_evidence / triples_total
    else:
        metrics["provenance_completeness"] = 0.0
    
    # Average confidence
    cursor = conn.execute("SELECT AVG(confidence) FROM triples WHERE confidence IS NOT NULL")
    row = cursor.fetchone()
    metrics["avg_triple_confidence"] = row[0] if row and row[0] is not None else None
    
    return metrics


def mcq_status_breakdown(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Get MCQ counts by status.
    
    Args:
        conn: Database connection
        
    Returns:
        Dict with status as keys and counts as values (e.g., {pending: x, approved: y, rejected: z})
    """
    cursor = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM mcqs
        GROUP BY status
    """)
    
    breakdown = {}
    for row in cursor.fetchall():
        status = row[0] or "pending"  # Handle NULL status
        count = row[1]
        breakdown[status] = count
    
    # Ensure all common statuses are present with 0 if missing
    for status in ["pending", "approved", "rejected"]:
        if status not in breakdown:
            breakdown[status] = 0
    
    return breakdown


def per_doc_summary(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Generate per-document summary statistics.
    
    Args:
        conn: Database connection
        
    Returns:
        List of dicts, each with keys:
        - doc_id, source_kind, pmid, doi
        - entities, triples, evidence_rows, mcqs
        - triples_with_evidence
    """
    summaries = []
    
    # Get all documents
    cursor = conn.execute("""
        SELECT doc_id, source_kind, pmid, doi
        FROM docs
        ORDER BY doc_id
    """)
    
    for row in cursor.fetchall():
        doc_id, source_kind, pmid, doi = row
        
        # Count entities for this doc
        cursor2 = conn.execute("SELECT COUNT(*) FROM entities WHERE doc_id = ?", (doc_id,))
        entities = cursor2.fetchone()[0]
        
        # Count triples (via entities in this doc)
        cursor2 = conn.execute("""
            SELECT COUNT(DISTINCT t.triple_id)
            FROM triples t
            INNER JOIN entities e1 ON t.head_entity = e1.entity_id
            INNER JOIN entities e2 ON t.tail_entity = e2.entity_id
            WHERE e1.doc_id = ? OR e2.doc_id = ?
        """, (doc_id, doc_id))
        triples = cursor2.fetchone()[0]
        
        # Count evidence rows for this doc
        cursor2 = conn.execute("SELECT COUNT(*) FROM evidence WHERE doc_id = ?", (doc_id,))
        evidence_rows = cursor2.fetchone()[0]
        
        # Count MCQs from triples in this doc
        cursor2 = conn.execute("""
            SELECT COUNT(DISTINCT m.mcq_id)
            FROM mcqs m
            INNER JOIN triples t ON m.triple_id = t.triple_id
            INNER JOIN entities e1 ON t.head_entity = e1.entity_id
            INNER JOIN entities e2 ON t.tail_entity = e2.entity_id
            WHERE e1.doc_id = ? OR e2.doc_id = ?
        """, (doc_id, doc_id))
        mcqs = cursor2.fetchone()[0]
        
        # Count triples with evidence for this doc
        cursor2 = conn.execute("""
            SELECT COUNT(DISTINCT t.triple_id)
            FROM triples t
            INNER JOIN evidence e ON t.triple_id = e.triple_id
            INNER JOIN entities e1 ON t.head_entity = e1.entity_id
            INNER JOIN entities e2 ON t.tail_entity = e2.entity_id
            WHERE e.doc_id = ? AND (e1.doc_id = ? OR e2.doc_id = ?)
        """, (doc_id, doc_id, doc_id))
        triples_with_evidence = cursor2.fetchone()[0]
        
        summaries.append({
            "doc_id": doc_id,
            "source_kind": source_kind or "",
            "pmid": pmid or "",
            "doi": doi or "",
            "entities": entities,
            "triples": triples,
            "evidence_rows": evidence_rows,
            "mcqs": mcqs,
            "triples_with_evidence": triples_with_evidence
        })
    
    return summaries


def render_table(rows: List[Dict[str, Any]], cols: List[str]) -> str:
    """
    Render a plain-text table from rows and columns.
    
    Args:
        rows: List of dictionaries (each dict is a row)
        cols: List of column names to display
        
    Returns:
        Plain-text table string
    """
    if not rows:
        return "No data."
    
    # Calculate column widths
    col_widths = {}
    for col in cols:
        # Width is at least the column header length
        col_widths[col] = len(col)
        # Check all row values for this column
        for row in rows:
            value = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], len(value))
    
    # Build header
    header_parts = []
    separator_parts = []
    for col in cols:
        width = col_widths[col]
        header_parts.append(col.ljust(width))
        separator_parts.append("-" * width)
    
    header = " | ".join(header_parts)
    separator = "-+-".join(separator_parts)
    
    # Build rows
    lines = [header, separator]
    for row in rows:
        row_parts = []
        for col in cols:
            width = col_widths[col]
            value = str(row.get(col, ""))
            row_parts.append(value.ljust(width))
        lines.append(" | ".join(row_parts))
    
    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate KG summary report")
    parser.add_argument("--db", default="kg.sqlite", help="Database path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    conn = open_conn(args.db)
    
    try:
        # Collect all metrics
        counts = overall_counts(conn)
        provenance = provenance_metrics(conn)
        mcq_status = mcq_status_breakdown(conn)
        doc_summaries = per_doc_summary(conn)
        
        if args.json:
            # Output as JSON
            report = {
                "overall_counts": counts,
                "provenance_metrics": provenance,
                "mcq_status_breakdown": mcq_status,
                "per_doc_summary": doc_summaries
            }
            print(json.dumps(report, indent=2))
        else:
            # Pretty text output
            print("=" * 60)
            print("KNOWLEDGE GRAPH SUMMARY REPORT")
            print("=" * 60)
            print()
            
            print("Overall Counts:")
            print("-" * 60)
            for key, value in counts.items():
                print(f"  {key:20s}: {value}")
            print()
            
            print("Provenance Metrics:")
            print("-" * 60)
            print(f"  Triples with evidence     : {provenance['triples_with_evidence']}")
            print(f"  Total triples              : {provenance['triples_total']}")
            print(f"  Provenance completeness    : {provenance['provenance_completeness']:.2%}")
            avg_conf = provenance['avg_triple_confidence']
            if avg_conf is not None:
                print(f"  Average triple confidence  : {avg_conf:.3f}")
            else:
                print(f"  Average triple confidence  : N/A")
            print()
            
            print("MCQ Status Breakdown:")
            print("-" * 60)
            for status, count in sorted(mcq_status.items()):
                print(f"  {status:20s}: {count}")
            print()
            
            if doc_summaries:
                print("Per-Document Summary:")
                print("-" * 60)
                table_cols = ["doc_id", "source_kind", "pmid", "entities", "triples", "evidence_rows", "mcqs", "triples_with_evidence"]
                print(render_table(doc_summaries, table_cols))
            else:
                print("Per-Document Summary: No documents found.")
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()

