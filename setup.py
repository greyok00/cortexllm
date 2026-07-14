#!/usr/bin/env python3
"""
CortexLLM — First-time setup.
Creates the database, config directory, and default config.
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config/cortexllm"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_PATH = CONFIG_DIR / "cortexllm.db"

DEFAULT_CONFIG = {
    "db_path": str(DB_PATH),
    "memory": {
        "hot_limit": 300,
        "warm_limit": 2000,
        "cold_limit": 50000
    },
    "heartbeat": {
        "interval_minutes": 30,
        "isolated_session": True
    },
    "mcp_server": {
        "port": 0,
        "transport": "stdio"
    }
}


def setup():
    print("CortexLLM Setup")
    print("=" * 40)

    # Create config directory
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Created {CONFIG_DIR}")

    # Write default config
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        print(f"  ✓ Created {CONFIG_FILE}")
    else:
        print(f"  • Config exists, skipping")

    # Initialize database
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cortexllm_db import db
    db.initialize()
    print(f"  ✓ Initialized database at {DB_PATH}")

    print()
    print("Setup complete. Run cortexllm_mcp_server.py to start.")
    return 0


if __name__ == "__main__":
    exit(setup())