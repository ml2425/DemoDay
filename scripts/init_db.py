#!/usr/bin/env python3
"""
Initialises or refreshes the SQLite database for DemoDay.
Reads SQL schema from database/schema.sql and creates kg.sqlite.
If configs/config.yaml exists and contains runtime.db_path, that path is used.
"""
import sqlite3, yaml
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "schema.sql"
CFG    = ROOT / "configs" / "config.yaml"

def get_db_path():
    default = ROOT / "kg.sqlite"
    if CFG.exists():
        try:
            cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
            return Path(cfg.get("runtime", {}).get("db_path", default))
        except Exception:
            return default
    return default

def main():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
        print(f"✅ Created/updated DB at {db_path}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
