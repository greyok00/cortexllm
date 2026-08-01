#!/usr/bin/env python3
"""
CortexLLM Database Layer — SQLite-native, WAL mode, single-writer/multi-reader.

Tables:
  - Checkpoints:     Session restore points (profile, timestamp, last_command, context)
  - Memory_Hot:      FIFO per-profile, capped at 300 rows (user prompts + responses)
  - Memory_Warm:     Per-profile context buffer, no hard cap (managed by distillation)
  - Memory_Cold:     Distilled facts + wiki layer — claim, evidence, provenance, conflict tracking
  - Active_Tasks:    Currently running tasks per profile
  - Logs:            Event log for observability

Wiki layer (inside Memory_Cold):
  - entity/attribute/provenance composite unique key for deterministic UPSERT conflict resolution
  - claim + evidence (JSON array) for structured knowledge
  - contradiction_flag + superseded_by for conflict tracking (never hard-delete)
  - last_verified + decay-weighted freshness scoring at query time

Connection model:
  - Exactly one writer connection (owned by the Dispatcher)
  - All other components use read-only connections
  - No shared connections across async tasks
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_DIR = Path.home() / ".config/cortexllm"
DB_PATH = DB_DIR / "cortexllm.db"

# Default freshness window: facts not re-verified within this many days are flagged stale
FRESHNESS_WINDOW_DAYS = 30

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA wal_autocheckpoint = 500;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Checkpoints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    last_command TEXT   NOT NULL,
    context     TEXT    DEFAULT '{}',
    session_id  TEXT,
    UNIQUE(profile, session_id)
);

CREATE TABLE IF NOT EXISTS Memory_Hot (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    role        TEXT    NOT NULL DEFAULT 'user',
    content     TEXT    NOT NULL,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    metadata    TEXT    DEFAULT '{}',
    platform    TEXT    DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS Memory_Warm (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    role        TEXT    NOT NULL DEFAULT 'user',
    content     TEXT    NOT NULL,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    metadata    TEXT    DEFAULT '{}',
    platform    TEXT    DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS Memory_Cold (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    profile             TEXT    NOT NULL,
    timestamp           TEXT    NOT NULL DEFAULT (datetime('now')),
    category            TEXT    NOT NULL,
    fact                TEXT    NOT NULL,
    source              TEXT    NOT NULL DEFAULT 'unknown',
    confidence          REAL    NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    tags                TEXT    DEFAULT '[]',
    metadata            TEXT    DEFAULT '{}',
    -- Wiki layer columns (added via migration, nullable for backward compat)
    entity              TEXT,
    attribute           TEXT,
    claim               TEXT,
    evidence            TEXT    DEFAULT '[]',
    provenance          TEXT    DEFAULT 'unknown',
    contradiction_flag  INTEGER DEFAULT 0,
    superseded_by       INTEGER DEFAULT NULL,
    last_verified       TEXT
);

CREATE TABLE IF NOT EXISTS Active_Tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT    NOT NULL,
    task_id     TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    progress    REAL    DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
    error       TEXT,
    metadata    TEXT    DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS Logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    event_type  TEXT    NOT NULL,
    event_data  TEXT    DEFAULT '{}',
    task_id     TEXT,
    session_id  TEXT
);

CREATE TABLE IF NOT EXISTS Worker_State (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    worker      TEXT    NOT NULL,
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL DEFAULT '{}',
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(worker, key)
);

CREATE TABLE IF NOT EXISTS Worker_Config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    worker      TEXT    NOT NULL,
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL DEFAULT '{}',
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(worker, key)
);

CREATE TABLE IF NOT EXISTS Earnings_Log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    worker      TEXT    NOT NULL,
    site        TEXT    NOT NULL,
    amount      REAL    NOT NULL DEFAULT 0,
    job_type    TEXT    DEFAULT 'unknown',
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT    DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_hot_profile ON Memory_Hot(profile, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_warm_profile ON Memory_Warm(profile, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cold_profile ON Memory_Cold(profile, category);
CREATE INDEX IF NOT EXISTS idx_tasks_profile ON Active_Tasks(profile, status);
CREATE INDEX IF NOT EXISTS idx_logs_profile ON Logs(profile, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_profile ON Checkpoints(profile, timestamp DESC);
"""

# ---------------------------------------------------------------------------
# Migration: add wiki columns to existing Memory_Cold table
# ---------------------------------------------------------------------------

MIGRATE_WIKI_COLUMNS = [
    ("entity", "TEXT"),
    ("attribute", "TEXT"),
    ("claim", "TEXT"),
    ("evidence", "TEXT DEFAULT '[]'"),
    ("provenance", "TEXT DEFAULT 'unknown'"),
    ("contradiction_flag", "INTEGER DEFAULT 0"),
    ("superseded_by", "INTEGER DEFAULT NULL"),
    ("last_verified", "TEXT"),
]

MIGRATE_WIKI_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cold_entity ON Memory_Cold(entity, attribute)",
    "CREATE INDEX IF NOT EXISTS idx_cold_provenance ON Memory_Cold(provenance)",
    "CREATE INDEX IF NOT EXISTS idx_cold_contradiction ON Memory_Cold(contradiction_flag)",
    "CREATE INDEX IF NOT EXISTS idx_cold_superseded ON Memory_Cold(superseded_by)",
    "CREATE INDEX IF NOT EXISTS idx_cold_last_verified ON Memory_Cold(last_verified)",
]


def _run_migration(conn: sqlite3.Connection):
    """Add wiki columns to existing Memory_Cold table if they don't exist."""
    cursor = conn.execute("PRAGMA table_info(Memory_Cold)")
    existing = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in MIGRATE_WIKI_COLUMNS:
        if col_name not in existing:
            conn.execute("ALTER TABLE Memory_Cold ADD COLUMN " + col_name + " " + col_type)
    for idx_sql in MIGRATE_WIKI_INDEXES:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass  # Index already exists
    conn.commit()


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------

class Database:
    """Single-writer / multi-reader database connection manager.

    Usage:
        db = Database()
        db.initialize()              # Create schema + run migrations
        db.writer.execute(...)       # One writer connection
        with db.reader() as conn:    # Read-only connections
            conn.execute(...)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._writer: Optional[sqlite3.Connection] = None
        self._readers = threading.local()
        self._reader_conns: set = set()
        self._reader_conns_lock = threading.Lock()
        self._init_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self):
        """Create the database and schema. Safe to call multiple times."""
        with self._init_lock:
            if self._writer is not None:
                return
            self._writer = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self._writer.row_factory = sqlite3.Row
            self._writer.executescript(SCHEMA_SQL)
            _run_migration(self._writer)

    @property
    def writer(self) -> sqlite3.Connection:
        """Return the single writer connection. Caller must commit."""
        if self._writer is None:
            self.initialize()
        return self._writer

    def reader(self) -> sqlite3.Connection:
        """Return a read-only connection for this thread."""
        if not hasattr(self._readers, 'conn') or self._readers.conn is None:
            conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON;")
            conn.execute("PRAGMA busy_timeout = 5000")
            self._readers.conn = conn
            with self._reader_conns_lock:
                self._reader_conns.add(conn)
        return self._readers.conn

    def close(self):
        """Close all connections."""
        if self._writer:
            self._writer.close()
            self._writer = None
        with self._reader_conns_lock:
            for conn in list(self._reader_conns):
                try:
                    conn.close()
                except Exception:
                    pass
            self._reader_conns.clear()
        if hasattr(self._readers, 'conn') and self._readers.conn:
            self._readers.conn = None

    # ------------------------------------------------------------------
    # Memory_Hot (FIFO per-profile, capped at 300)
    # ------------------------------------------------------------------

    def add_to_hot(self, profile: str, role: str, content: str,
                   tokens_in: int = 0, tokens_out: int = 0,
                   metadata: dict = None, platform: str = "default") -> int:
        """Add a message to Memory_Hot. Enforces 300-row FIFO cap per profile."""
        w = self.writer
        cursor = w.execute(
            "INSERT INTO Memory_Hot (profile, role, content, tokens_in, tokens_out, metadata, platform) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile, role, content, tokens_in, tokens_out,
             json.dumps(metadata or {}), platform)
        )
        row_id = cursor.lastrowid

        # FIFO cap: delete oldest rows beyond 300 for this profile
        w.execute(
            "DELETE FROM Memory_Hot WHERE id IN ("
            "  SELECT id FROM Memory_Hot WHERE profile = ? "
            "  ORDER BY timestamp DESC LIMIT -1 OFFSET 300"
            ")",
            (profile,)
        )
        w.commit()
        return row_id

    def get_hot(self, profile: str, limit: int = 50) -> List[Dict]:
        """Get most recent Memory_Hot rows for a profile."""
        rows = self.reader().execute(
            "SELECT * FROM Memory_Hot WHERE profile = ? ORDER BY timestamp DESC LIMIT ?",
            (profile, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_last_command(self, profile: str) -> Optional[str]:
        """Get the most recent user command for a profile."""
        row = self.reader().execute(
            "SELECT content FROM Memory_Hot "
            "WHERE profile = ? AND role = 'user' "
            "ORDER BY timestamp DESC LIMIT 1",
            (profile,)
        ).fetchone()
        return row["content"] if row else None

    # ------------------------------------------------------------------
    # Memory_Warm
    # ------------------------------------------------------------------

    def add_to_warm(self, profile: str, role: str, content: str,
                    tokens_in: int = 0, tokens_out: int = 0,
                    metadata: dict = None, platform: str = "default") -> int:
        """Add a message to Memory_Warm."""
        w = self.writer
        cursor = w.execute(
            "INSERT INTO Memory_Warm (profile, role, content, tokens_in, tokens_out, metadata, platform) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile, role, content, tokens_in, tokens_out,
             json.dumps(metadata or {}), platform)
        )
        w.commit()
        return cursor.lastrowid

    def get_warm(self, profile: str, limit: int = 100) -> List[Dict]:
        """Get most recent Memory_Warm rows for a profile."""
        rows = self.reader().execute(
            "SELECT * FROM Memory_Warm WHERE profile = ? ORDER BY timestamp DESC LIMIT ?",
            (profile, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Memory_Cold — Wiki Layer (distilled facts + structured knowledge)
    # ------------------------------------------------------------------
    #
    # The wiki layer extends Memory_Cold with structured knowledge fields:
    #   entity, attribute, claim, evidence (JSON array), provenance,
    #   contradiction_flag, superseded_by, last_verified.
    #
    # Conflict resolution uses SQLite UPSERT keyed on (entity, attribute, provenance).
    # On conflict: the older row is flagged (contradiction_flag=1) and its
    # superseded_by points to the new row. Both rows are preserved for provenance.
    #
    # Freshness is computed at query time via decay-weighted scoring based on
    # last_verified. Facts not re-verified within FRESHNESS_WINDOW_DAYS are
    # flagged as stale but never auto-deleted.
    # ------------------------------------------------------------------

    def add_to_cold(self, profile: str, category: str, fact: str,
                    source: str = "unknown", confidence: float = 0.5,
                    tags: list = None, metadata: dict = None) -> int:
        """Add a distilled fact to Memory_Cold. Source/confidence/tags required."""
        w = self.writer
        now = datetime.utcnow().isoformat()
        cursor = w.execute(
            "INSERT INTO Memory_Cold (profile, category, fact, source, confidence, tags, metadata, last_verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (profile, category, fact, source, confidence,
             json.dumps(tags or []), json.dumps(metadata or {}), now)
        )
        w.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Wiki: add structured claim with UPSERT conflict resolution
    # ------------------------------------------------------------------

    def add_wiki_fact(self, entity: str, attribute: str, claim: str,
                      profile: str = "shared", category: str = "wiki",
                      evidence: list = None, provenance: str = "unknown",
                      confidence: float = 0.5, source: str = "unknown",
                      tags: list = None, metadata: dict = None) -> int:
        """Add a wiki fact with UPSERT conflict resolution.

        Keyed on (entity, attribute, provenance). On conflict:
        - The existing row is flagged (contradiction_flag=1)
        - Its superseded_by points to the new row
        - Both rows are preserved for provenance
        """
        w = self.writer
        now = datetime.utcnow().isoformat()

        w.execute("BEGIN IMMEDIATE")
        try:
            # First: flag any existing non-flagged row for this key as contradicted
            w.execute(
                "UPDATE Memory_Cold SET contradiction_flag = 1, "
                "  metadata = json_set(COALESCE(metadata, '{}'), '$.superseded_at', ?) "
                "WHERE entity = ? AND attribute = ? AND provenance = ? AND contradiction_flag = 0",
                (now, entity, attribute, provenance)
            )
            # Get the ID of the row we just flagged (if any)
            old_row = w.execute(
                "SELECT id FROM Memory_Cold "
                "WHERE entity = ? AND attribute = ? AND provenance = ? AND contradiction_flag = 1 "
                "  AND json_extract(COALESCE(metadata, '{}'), '$.superseded_at') = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (entity, attribute, provenance, now)
            ).fetchone()
            old_id = old_row["id"] if old_row else None

            # Insert the new row — fact stores a summary, claim stores the actual claim text
            cursor = w.execute(
                "INSERT INTO Memory_Cold "
                "  (profile, category, fact, source, confidence, tags, metadata, "
                "   entity, attribute, claim, evidence, provenance, last_verified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (profile, category, entity + ": " + attribute, source, confidence,
                 json.dumps(tags or []), json.dumps(metadata or {}),
                 entity, attribute, claim,
                 json.dumps(evidence or []), provenance, now)
            )
            new_id = cursor.lastrowid

            # If we flagged an old row, point its superseded_by at the new row
            if old_id:
                w.execute(
                    "UPDATE Memory_Cold SET superseded_by = ? WHERE id = ?",
                    (new_id, old_id)
                )

            w.commit()
        except Exception:
            w.rollback()
            raise
        return new_id

    def get_wiki_fact(self, entity: str, attribute: str,
                      provenance: str = None) -> Optional[Dict]:
        """Get the current (non-contradicted) wiki fact for an entity/attribute.

        If provenance is specified, returns the fact for that platform only.
        Otherwise returns the most recent across all platforms.
        """
        if provenance:
            rows = self.reader().execute(
                "SELECT * FROM Memory_Cold "
                "WHERE entity = ? AND attribute = ? AND provenance = ? AND contradiction_flag = 0 "
                "ORDER BY timestamp DESC LIMIT 1",
                (entity, attribute, provenance)
            ).fetchall()
        else:
            rows = self.reader().execute(
                "SELECT * FROM Memory_Cold "
                "WHERE entity = ? AND attribute = ? AND contradiction_flag = 0 "
                "ORDER BY timestamp DESC LIMIT 1",
                (entity, attribute)
            ).fetchall()
        return dict(rows[0]) if rows else None

    def search_wiki(self, query: str, limit: int = 20) -> List[Dict]:
        """Search wiki facts by entity, attribute, or claim text.

        Results are ranked by a decay-weighted freshness score:
          score = confidence * decay_factor
          decay_factor = max(0, 1 - (days_since_verified / FRESHNESS_WINDOW_DAYS))

        Facts not verified within FRESHNESS_WINDOW_DAYS are flagged as stale
        but still returned (with stale=True) — never auto-deleted.
        """
        like_q = "%" + query + "%"
        rows = self.reader().execute(
            "SELECT *, "
            "  julianday('now') - julianday(COALESCE(last_verified, timestamp)) "
            "    AS days_since_verified "
            "FROM Memory_Cold "
            "WHERE contradiction_flag = 0 AND superseded_by IS NULL "
            "  AND (entity LIKE ? OR attribute LIKE ? OR claim LIKE ? OR fact LIKE ?) "
            "ORDER BY timestamp DESC LIMIT ?",
            (like_q, like_q, like_q, like_q, limit)
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            days = d.pop("days_since_verified", FRESHNESS_WINDOW_DAYS)
            decay = max(0.0, 1.0 - (days / FRESHNESS_WINDOW_DAYS))
            d["freshness_score"] = round(d.get("confidence", 0.5) * decay, 4)
            d["stale"] = days > FRESHNESS_WINDOW_DAYS
            results.append(d)

        results.sort(key=lambda x: x["freshness_score"], reverse=True)
        return results

    def get_cold(self, profile: str, category: str = None, limit: int = 50) -> List[Dict]:
        """Get Memory_Cold facts for a profile, optionally filtered by category."""
        if category:
            rows = self.reader().execute(
                "SELECT * FROM Memory_Cold WHERE profile = ? AND category = ? "
                "AND contradiction_flag = 0 AND superseded_by IS NULL "
                "ORDER BY timestamp DESC LIMIT ?",
                (profile, category, limit)
            ).fetchall()
        else:
            rows = self.reader().execute(
                "SELECT * FROM Memory_Cold WHERE profile = ? "
                "AND contradiction_flag = 0 AND superseded_by IS NULL "
                "ORDER BY timestamp DESC LIMIT ?",
                (profile, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Conflict reconciliation
    # ------------------------------------------------------------------

    def get_unresolved_contradictions(self, limit: int = 50) -> List[Dict]:
        """Get all rows flagged as contradicted whose superseder is also contradicted,
        forming a chain that needs reconciliation."""
        rows = self.reader().execute(
            "SELECT c1.*, c2.claim AS superseder_claim, c2.confidence AS superseder_confidence "
            "FROM Memory_Cold c1 "
            "LEFT JOIN Memory_Cold c2 ON c1.superseded_by = c2.id "
            "WHERE c1.contradiction_flag = 1 "
            "  AND (c2.contradiction_flag = 1 OR c2.id IS NULL) "
            "ORDER BY c1.timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def reconcile_contradiction(self, entity: str, attribute: str,
                                winning_id: int, provenance: str = None) -> bool:
        """Resolve a contradiction chain by marking the winner as authoritative
        and clearing contradiction_flag on all other rows in the chain.

        Returns True if any rows were updated.
        """
        w = self.writer
        # Clear contradiction_flag on the winner
        cursor = w.execute(
            "UPDATE Memory_Cold SET contradiction_flag = 0, "
            "  metadata = json_set(COALESCE(metadata, '{}'), '$.reconciled_at', datetime('now')) "
            "WHERE id = ?",
            (winning_id,)
        )
        if cursor.rowcount == 0:
            w.commit()
            return False
        # Mark all other rows in this chain as resolved (clear flag, point to winner)
        if provenance:
            w.execute(
                "UPDATE Memory_Cold SET contradiction_flag = 0, "
                "  metadata = json_set(COALESCE(metadata, '{}'), '$.reconciled_by', ?) "
                "WHERE entity = ? AND attribute = ? AND provenance = ? AND id != ? AND contradiction_flag = 1",
                (winning_id, entity, attribute, provenance, winning_id)
            )
        else:
            w.execute(
                "UPDATE Memory_Cold SET contradiction_flag = 0, "
                "  metadata = json_set(COALESCE(metadata, '{}'), '$.reconciled_by', ?) "
                "WHERE entity = ? AND attribute = ? AND id != ? AND contradiction_flag = 1",
                (winning_id, entity, attribute, winning_id)
            )
        w.commit()
        return True

    # ------------------------------------------------------------------
    # Freshness: verify a fact (touch last_verified)
    # ------------------------------------------------------------------

    def verify_fact(self, fact_id: int) -> bool:
        """Update last_verified to now for a fact. Returns True if updated."""
        w = self.writer
        cursor = w.execute(
            "UPDATE Memory_Cold SET last_verified = datetime('now') WHERE id = ?",
            (fact_id,)
        )
        w.commit()
        return cursor.rowcount > 0

    def get_stale_facts(self, window_days: int = None, limit: int = 100) -> List[Dict]:
        """Get facts not verified within the window. Never auto-deletes."""
        window = window_days if window_days is not None else FRESHNESS_WINDOW_DAYS
        rows = self.reader().execute(
            "SELECT * FROM Memory_Cold "
            "WHERE contradiction_flag = 0 AND superseded_by IS NULL "
            "  AND (last_verified IS NULL "
            "    OR julianday('now') - julianday(last_verified) > ?) "
            "ORDER BY last_verified ASC NULLS FIRST LIMIT ?",
            (window, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Worker_State (per-worker key-value store)
    # ------------------------------------------------------------------

    def set_worker_state(self, worker: str, key: str, value: Any):
        """Set a worker state value (upsert)."""
        w = self.writer
        w.execute(
            "INSERT INTO Worker_State (worker, key, value, updated_at) VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(worker, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (worker, key, json.dumps(value))
        )
        w.commit()

    def get_worker_state(self, worker: str, key: str, default: Any = None) -> Any:
        """Get a worker state value."""
        row = self.reader().execute(
            "SELECT value FROM Worker_State WHERE worker = ? AND key = ?",
            (worker, key)
        ).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return default

    def get_all_worker_state(self, worker: str) -> Dict:
        """Get all state for a worker."""
        rows = self.reader().execute(
            "SELECT key, value FROM Worker_State WHERE worker = ?",
            (worker,)
        ).fetchall()
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                result[r["key"]] = r["value"]
        return result

    # ------------------------------------------------------------------
    # Worker_Config (per-worker configuration)
    # ------------------------------------------------------------------

    def set_worker_config(self, worker: str, key: str, value: Any):
        """Set a worker config value (upsert)."""
        w = self.writer
        w.execute(
            "INSERT INTO Worker_Config (worker, key, value, updated_at) VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(worker, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (worker, key, json.dumps(value))
        )
        w.commit()

    def get_worker_config(self, worker: str, key: str, default: Any = None) -> Any:
        """Get a worker config value."""
        row = self.reader().execute(
            "SELECT value FROM Worker_Config WHERE worker = ? AND key = ?",
            (worker, key)
        ).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return default

    def get_all_worker_config(self, worker: str) -> Dict:
        """Get all config for a worker."""
        rows = self.reader().execute(
            "SELECT key, value FROM Worker_Config WHERE worker = ?",
            (worker,)
        ).fetchall()
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                result[r["key"]] = r["value"]
        return result

    # ------------------------------------------------------------------
    # Earnings_Log
    # ------------------------------------------------------------------

    def log_earnings(self, worker: str, site: str, amount: float,
                     job_type: str = "unknown", metadata: dict = None):
        """Log an earnings entry."""
        w = self.writer
        w.execute(
            "INSERT INTO Earnings_Log (worker, site, amount, job_type, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (worker, site, amount, job_type, json.dumps(metadata or {}))
        )
        w.commit()

    def get_earnings(self, worker: str = None, site: str = None,
                     since: str = None) -> List[Dict]:
        """Get earnings entries, optionally filtered."""
        conditions = []
        params = []
        if worker:
            conditions.append("worker = ?")
            params.append(worker)
        if site:
            conditions.append("site = ?")
            params.append(site)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1"
        rows = self.reader().execute(
            "SELECT * FROM Earnings_Log WHERE " + where + " ORDER BY timestamp DESC",
            params
        ).fetchall()
        return [dict(r) for r in rows]

    def get_earnings_summary(self, worker: str = None,
                              since: str = None) -> Dict:
        """Get earnings summary (total per site)."""
        conditions = []
        params = []
        if worker:
            conditions.append("worker = ?")
            params.append(worker)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1"
        rows = self.reader().execute(
            "SELECT site, SUM(amount) as total, COUNT(*) as count "
            "FROM Earnings_Log WHERE " + where + " GROUP BY site ORDER BY total DESC",
            params
        ).fetchall()
        return {r["site"]: {"total": r["total"], "count": r["count"]} for r in rows}

    # ------------------------------------------------------------------
    # Checkpoints (restore/resume)
    # ------------------------------------------------------------------

    def save_checkpoint(self, profile: str, last_command: str,
                        context: dict = None, session_id: str = None) -> int:
        """Save a checkpoint for restore/resume."""
        w = self.writer
        cursor = w.execute(
            "INSERT OR REPLACE INTO Checkpoints (profile, last_command, context, session_id) "
            "VALUES (?, ?, ?, ?)",
            (profile, last_command, json.dumps(context or {}), session_id)
        )
        w.commit()
        return cursor.lastrowid

    def get_checkpoint(self, profile: str) -> Optional[Dict]:
        """Get the latest checkpoint for a profile."""
        row = self.reader().execute(
            "SELECT * FROM Checkpoints WHERE profile = ? ORDER BY timestamp DESC LIMIT 1",
            (profile,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Active_Tasks
    # ------------------------------------------------------------------

    def add_task(self, profile: str, task_id: str, description: str,
                 metadata: dict = None) -> int:
        """Register a new task."""
        w = self.writer
        cursor = w.execute(
            "INSERT INTO Active_Tasks (profile, task_id, description, metadata) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET description = excluded.description, "
            "  metadata = excluded.metadata, updated_at = datetime('now')",
            (profile, task_id, description, json.dumps(metadata or {}))
        )
        w.commit()
        return cursor.lastrowid

    def update_task(self, task_id: str, status: str = None,
                    progress: float = None, error: str = None) -> bool:
        """Update task status/progress/error."""
        updates = []
        params = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        if not updates:
            return False
        updates.append("updated_at = datetime('now')")
        params.append(task_id)
        w = self.writer
        w.execute(
            "UPDATE Active_Tasks SET " + ", ".join(updates) + " WHERE task_id = ?",
            params
        )
        w.commit()
        return True

    def get_tasks(self, profile: str = None, status: str = None) -> List[Dict]:
        """Get tasks, optionally filtered by profile and/or status."""
        conditions = []
        params = []
        if profile:
            conditions.append("profile = ?")
            params.append(profile)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1"
        rows = self.reader().execute(
            "SELECT * FROM Active_Tasks WHERE " + where + " ORDER BY created_at DESC",
            params
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def log_event(self, profile: str, event_type: str,
                  event_data: dict = None, task_id: str = None,
                  session_id: str = None) -> int:
        """Write an event to the Logs table."""
        w = self.writer
        cursor = w.execute(
            "INSERT INTO Logs (profile, event_type, event_data, task_id, session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (profile, event_type, json.dumps(event_data or {}), task_id, session_id)
        )
        w.commit()
        return cursor.lastrowid

    def get_logs(self, profile: str = None, event_type: str = None,
                 limit: int = 100) -> List[Dict]:
        """Get recent log entries."""
        conditions = []
        params = []
        if profile:
            conditions.append("profile = ?")
            params.append(profile)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        where = " AND ".join(conditions) if conditions else "1"
        rows = self.reader().execute(
            "SELECT * FROM Logs WHERE " + where + " ORDER BY timestamp DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

db = Database()
