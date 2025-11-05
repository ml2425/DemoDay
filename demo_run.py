#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
import sqlite3
from typing import List

# --- Project imports (existing in your repo) ---
from pipeline.ingest import Ingest
from pipeline.graph import build_graph
from scripts.report_summary import (
    open_conn, overall_counts, provenance_metrics, mcq_status_breakdown, per_doc_summary, render_table
)

def max_doc_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(doc_id), 0) FROM docs").fetchone()
    return int(row[0] or 0)

def find_new_doc_ids(conn: sqlite3.Connection, after_id: int) -> List[int]:
    rows = conn.execute("SELECT doc_id FROM docs WHERE doc_id > ? ORDER BY doc_id ASC", (after_id,)).fetchall()
    return [int(r[0]) for r in rows]

def demo():
    ap = argparse.ArgumentParser(
        description="VM2Q end-to-end demo (ingest → orchestrate → review/report)",
        epilog="Example: python demo_run.py --source pdf --pdf samples/Meningioma_clinical_molecular_.pdf"
    )
    ap.add_argument("--db", default="kg.sqlite", help="SQLite database path (default: kg.sqlite)")
    ap.add_argument("--source", choices=["pdf", "pubmed"], required=True, help="Choose one ingestion source for this demo run")
    ap.add_argument("--pdf", nargs="+", help="One or more PDF paths (when --source pdf)")
    ap.add_argument("--query", help="PubMed query string (when --source pubmed)")
    ap.add_argument("--max-results", type=int, default=2, help="Max PubMed results (default: 2)")
    ap.add_argument("--demo-text", default="Temozolomide treats glioblastoma. MRI evaluates tumor recurrence.",
                    help="Short text to run through the pipeline for each new doc (default: a glioma-themed sentence)")
    ap.add_argument("--ui", action="store_true", help="Launch Gradio review UI at the end")
    ap.add_argument("--json", action="store_true", help="Print JSON report instead of tables at the end")
    args = ap.parse_args()

    # 0) Connect DB
    conn = open_conn(args.db)
    before = max_doc_id(conn)

    # 1) Ingest (PDF or PubMed)
    ing = Ingest(db_path=args.db)
    if args.source == "pdf":
        if not args.pdf:
            print("ERROR: --pdf paths required when --source pdf", file=sys.stderr)
            sys.exit(2)
        print(f"[Ingest] PDFs → {args.pdf}")
        docs = ing.from_pdf(args.pdf)
    else:
        if not args.query:
            print("ERROR: --query required when --source pubmed", file=sys.stderr)
            sys.exit(2)
        print(f"[Ingest] PubMed → '{args.query}' (max {args.max_results})")
        docs = ing.from_pubmed(args.query, max_results=args.max_results)

    # 2) Identify newly added docs
    new_ids = find_new_doc_ids(conn, after_id=before)
    if not new_ids:
        print("No new documents detected (they might already be in the DB).", file=sys.stderr)
        print("Tip: change the PDF list or PubMed query, or clear the DB if this is a fresh demo.")
        # Continue anyway to show reporting
    else:
        print(f"[Ingest] New doc_ids: {new_ids}")

    # 3) Orchestrate each new document
    orch = build_graph(db_path=args.db)
    for doc in docs:
        if doc.doc_id in new_ids:
            # Use actual PDF text if available, otherwise use demo text
            text_to_process = doc.text if doc.text else args.demo_text
            print(f"[Run] Orchestrating doc_id={doc.doc_id}")
            if doc.text:
                print(f"      Processing {len(text_to_process)} characters from PDF...")
            else:
                print(f"      Using demo text: '{args.demo_text}'")
            out = orch.run_doc(doc_id=doc.doc_id, text=text_to_process)
            print(f"      → Created: sentences={out['sentences_processed']}, triples={out['triples_created']}, mcqs={out['mcqs_created']}")

    # 4) Optional: Launch the review UI
    if args.ui:
        try:
            from pipeline.ui_gradio import launch_review_ui
            print("[UI] Launching Gradio MCQ review at http://127.0.0.1:7860 … (Ctrl+C to stop)")
            interface = launch_review_ui(db_path=args.db)
            interface.launch(server_port=7860)
        except Exception as e:
            print(f"[UI] Failed to launch UI: {e}", file=sys.stderr)

    # 5) Reporting (tables or JSON)
    summary = {
        "overall": overall_counts(conn),
        "provenance": provenance_metrics(conn),
        "mcqs": mcq_status_breakdown(conn),
        "per_doc": per_doc_summary(conn),
    }
    if args.json:
        import json
        print(json.dumps(summary, indent=2))
    else:
        print("\n# Overall")
        print(render_table([summary["overall"]], list(summary["overall"].keys())))
        print("\n# Provenance")
        print(render_table([summary["provenance"]], list(summary["provenance"].keys())))
        print("\n# MCQ Status")
        print(render_table([summary["mcqs"]], ["pending","approved","rejected","total"]))
        print("\n# Per Document")
        cols = ["doc_id","source_kind","pmid","doi","entities","triples","evidence_rows","triples_with_evidence","mcqs"]
        print(render_table(summary["per_doc"], cols))

    # Cleanup
    if 'orch' in locals():
        orch.conn.close()
    conn.close()

if __name__ == "__main__":
    demo()
