#!/usr/bin/env python3
"""
Tiny CLI for listing and reviewing pending MCQs.
Headless review tool for smoke testing.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_utils import connect
from database.mcq_utils import list_mcqs, update_mcq_status


def main():
    parser = argparse.ArgumentParser(description="Review pending MCQs")
    parser.add_argument("--db", default="kg.sqlite", help="Database path")
    parser.add_argument("--list", action="store_true", help="List pending MCQs")
    parser.add_argument("--approve", type=int, help="Approve MCQ by ID")
    parser.add_argument("--reject", type=int, help="Reject MCQ by ID")
    parser.add_argument("--feedback", type=str, default="", help="Feedback text")
    
    args = parser.parse_args()
    
    conn = connect(args.db)
    
    try:
        if args.list:
            mcqs = list_mcqs(conn, status="pending", limit=20)
            if not mcqs:
                print("No pending MCQs found.")
                return
            
            print(f"Found {len(mcqs)} pending MCQs:\n")
            for mcq in mcqs:
                print(f"ID: {mcq['mcq_id']} | Stem: {mcq['stem'][:60]}...")
        
        elif args.approve:
            update_mcq_status(conn, args.approve, "approved", args.feedback)
            print(f"MCQ {args.approve} approved.")
        
        elif args.reject:
            update_mcq_status(conn, args.reject, "rejected", args.feedback)
            print(f"MCQ {args.reject} rejected.")
        
        else:
            parser.print_help()
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()

