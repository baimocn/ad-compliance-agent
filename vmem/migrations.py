"""
vmem schema migrations framework.

Provides run_migrations(conn) to apply pending migrations tracked in
schema_migrations table. All DDL uses CREATE TABLE IF NOT EXISTS for
idempotency (D-01). No down migrations / rollback (D-11).
"""

import json
import sqlite3
import time


# ---------------------------------------------------------------------------
# Migration 001 — schema_migrations (no-op marker)
# The actual CREATE TABLE IF NOT EXISTS for schema_migrations is in
# run_migrations() itself, before any migration runs. This entry exists
# solely so the MIGRATIONS list records the schema_migrations table
# creation in the tracking table.
# ---------------------------------------------------------------------------

def _migrate_001(conn: sqlite3.Connection) -> None:
    """001 — schema_migrations marker (created by run_migrations before this runs)."""
    pass


# ---------------------------------------------------------------------------
# Migration 002 — user_profiles (DATA-02)
# ---------------------------------------------------------------------------

def _migrate_002(conn: sqlite3.Connection) -> None:
    """002 — user_profiles table with self-referential hierarchy."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            name TEXT NOT NULL,
            level TEXT DEFAULT '',
            created_at INTEGER NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES user_profiles(id)
        )
    """)
    # D-12: single-column index on FK column
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_profiles_parent_id
        ON user_profiles(parent_id)
    """)


# ---------------------------------------------------------------------------
# Migration 003 — profile_attributes (DATA-03)
# ---------------------------------------------------------------------------

def _migrate_003(conn: sqlite3.Connection) -> None:
    """003 — profile_attributes table with FTS5 trigram index."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profile_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            attr_key TEXT NOT NULL,
            attr_value TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            source TEXT DEFAULT '',
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES user_profiles(id)
        )
    """)
    # D-12: single-column indexes on FK and category
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_profile_attr_profile_id
        ON profile_attributes(profile_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_profile_attr_category
        ON profile_attributes(category)
    """)
    # D-14: FTS5 virtual table with trigram tokenizer
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS profile_attr_fts USING fts5(
            attr_key, attr_value,
            content='profile_attributes',
            content_rowid='id',
            tokenize='trigram'
        )
    """)


# ---------------------------------------------------------------------------
# Migration 004 — causal_links (DATA-04)
# ---------------------------------------------------------------------------

def _migrate_004(conn: sqlite3.Connection) -> None:
    """004 — causal_links table with composite index and FTS5."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS causal_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (from_id) REFERENCES memory_vectors(key),
            FOREIGN KEY (to_id) REFERENCES memory_vectors(key)
        )
    """)
    # D-12: single-column indexes on FK columns
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_causal_links_from_id
        ON causal_links(from_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_causal_links_to_id
        ON causal_links(to_id)
    """)
    # D-13: composite index
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_causal_links_from_relation
        ON causal_links(from_id, relation)
    """)
    # D-14: FTS5 virtual table on relation column
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS causal_links_fts USING fts5(
            relation,
            content='causal_links',
            content_rowid='id',
            tokenize='trigram'
        )
    """)


# ---------------------------------------------------------------------------
# Migration 005 — memory_links (DATA-06)
# ---------------------------------------------------------------------------

def _migrate_005(conn: sqlite3.Connection) -> None:
    """005 — memory_links table with composite index."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (from_id) REFERENCES memory_vectors(key),
            FOREIGN KEY (to_id) REFERENCES memory_vectors(key)
        )
    """)
    # D-12: single-column indexes on FK columns
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_links_from_id
        ON memory_links(from_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_links_to_id
        ON memory_links(to_id)
    """)
    # D-13: composite index
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_links_from_type
        ON memory_links(from_id, link_type)
    """)


# ---------------------------------------------------------------------------
# Migration 006 — closure_table (DATA-05)
# ---------------------------------------------------------------------------

def _migrate_006(conn: sqlite3.Connection) -> None:
    """006 — closure_table for fast ancestor queries."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS closure_table (
            ancestor TEXT NOT NULL,
            descendant TEXT NOT NULL,
            depth INTEGER NOT NULL,
            PRIMARY KEY (ancestor, descendant),
            FOREIGN KEY (ancestor) REFERENCES memory_vectors(key),
            FOREIGN KEY (descendant) REFERENCES memory_vectors(key)
        )
    """)
    # D-12: single-column indexes on FK columns
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_closure_ancestor
        ON closure_table(ancestor)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_closure_descendant
        ON closure_table(descendant)
    """)


# ---------------------------------------------------------------------------
# Migration 007 — topics (DATA-07)
# ---------------------------------------------------------------------------

def _migrate_007(conn: sqlite3.Connection) -> None:
    """007 — topics table with BLOB centroid (float32[512])."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            centroid BLOB,
            session_count INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    """)
    # No FK indexes needed — no FK to memory_vectors.
    # D-15: centroid BLOB, full-table cosine scan for topic count < 100.


# ---------------------------------------------------------------------------
# Migration 008 — session_topics (DATA-08)
# ---------------------------------------------------------------------------

def _migrate_008(conn: sqlite3.Connection) -> None:
    """008 — session_topics join table."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            topic_id INTEGER NOT NULL,
            similarity REAL NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)
    # D-12: single-column indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_topics_session_id
        ON session_topics(session_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_topics_topic_id
        ON session_topics(topic_id)
    """)


# ---------------------------------------------------------------------------
# Migration 009 — decay_state (DATA-09)
# ---------------------------------------------------------------------------

def _migrate_009(conn: sqlite3.Connection) -> None:
    """009 — decay_state table for FSRS-4.5 parameters."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decay_state (
            memory_key TEXT PRIMARY KEY,
            difficulty REAL DEFAULT 0.0,
            stability REAL DEFAULT 0.0,
            retrievability REAL DEFAULT 1.0,
            last_review INTEGER,
            FOREIGN KEY (memory_key) REFERENCES memory_vectors(key)
        )
    """)
    # D-12: explicit index on PK FK (technically redundant but per spec)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_decay_state_memory_key
        ON decay_state(memory_key)
    """)


# ---------------------------------------------------------------------------
# Migration 010 — column cleanup on memory_vectors (D-05, D-06, D-07)
# ---------------------------------------------------------------------------

def _migrate_010_cleanup_memory_vectors(conn: sqlite3.Connection) -> None:
    """010 — Drop access_count (D-05), rename level->importance (D-06), convert tags to JSON (D-07)."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(memory_vectors)").fetchall()}

    # D-05: Drop access_count column (only if it exists)
    if "access_count" in columns:
        conn.execute("ALTER TABLE memory_vectors DROP COLUMN access_count")

    # D-06: Rename level -> importance (only if level column exists)
    if "level" in columns:
        conn.execute("ALTER TABLE memory_vectors RENAME COLUMN level TO importance")

    # D-07: Convert tags from comma-separated to JSON array
    rows = conn.execute(
        "SELECT key, tags FROM memory_vectors WHERE tags != '' AND tags IS NOT NULL"
    ).fetchall()
    for key, tags_str in rows:
        try:
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            tags_json = json.dumps(tag_list, ensure_ascii=False)
            conn.execute("UPDATE memory_vectors SET tags = ? WHERE key = ?", (tags_json, key))
        except (json.JSONDecodeError, AttributeError):
            pass  # already JSON or empty


# ---------------------------------------------------------------------------
# Migration 011 — unique index on profile_attributes (PROF-01)
# ---------------------------------------------------------------------------

def _migrate_011_add_profile_unique_index(conn: sqlite3.Connection) -> None:
    """011 — Unique index on profile_attributes(profile_id, attr_key) for upsert."""
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_attr_unique
        ON profile_attributes(profile_id, attr_key)
    """)


# ---------------------------------------------------------------------------
# Migration 012 — add confidence column to memory_vectors (CONF-01)
# ---------------------------------------------------------------------------

def _migrate_012_add_confidence_column(conn: sqlite3.Connection) -> None:
    """012 — Add confidence REAL DEFAULT 0.5 to memory_vectors."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(memory_vectors)").fetchall()}
    if "confidence" not in columns:
        conn.execute("ALTER TABLE memory_vectors ADD COLUMN confidence REAL DEFAULT 0.5")


# ---------------------------------------------------------------------------
# Migration 013 — confidence_log table (CONF-05)
# ---------------------------------------------------------------------------

def _migrate_013_create_confidence_log(conn: sqlite3.Connection) -> None:
    """013 — confidence_log table for tracking confidence changes."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS confidence_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT NOT NULL,
            old_confidence REAL,
            new_confidence REAL NOT NULL,
            delta REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (memory_key) REFERENCES memory_vectors(key)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_confidence_log_key
        ON confidence_log(memory_key)
    """)


# ---------------------------------------------------------------------------
# MIGRATIONS registry
# ---------------------------------------------------------------------------

MIGRATIONS = [
    ("001_schema_migrations", _migrate_001),
    ("002_user_profiles", _migrate_002),
    ("003_profile_attributes", _migrate_003),
    ("004_causal_links", _migrate_004),
    ("005_memory_links", _migrate_005),
    ("006_closure_table", _migrate_006),
    ("007_topics", _migrate_007),
    ("008_session_topics", _migrate_008),
    ("009_decay_state", _migrate_009),
    ("010_cleanup_memory_vectors", _migrate_010_cleanup_memory_vectors),
    ("011_profile_unique_index", _migrate_011_add_profile_unique_index),
    ("012_add_confidence_column", _migrate_012_add_confidence_column),
    ("013_create_confidence_log", _migrate_013_create_confidence_log),
]


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

def run_migrations(conn: sqlite3.Connection) -> None:
    """Execute pending migrations in order. Idempotent.

    Creates schema_migrations table if needed, then applies any migration
    whose name is not yet recorded. Each migration runs inside its own
    commit for crash safety (D-10, D-11).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name TEXT PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """)
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute(
            "SELECT migration_name FROM schema_migrations"
        ).fetchall()
    }

    for name, func in MIGRATIONS:
        if name not in applied:
            func(conn)
            conn.execute(
                "INSERT INTO schema_migrations (migration_name, applied_at) VALUES (?, ?)",
                (name, int(time.time())),
            )
            conn.commit()
