"""Initialize database schema."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.db_utils import init_db

if __name__ == "__main__":
    init_db()
    print("[OK] Database initialization complete")

