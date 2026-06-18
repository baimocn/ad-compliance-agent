"""
审查记录与反馈存储 — SQLite
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional


class ReviewStore:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "pipeline" / "data" / "review.db")
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    overall_risk TEXT NOT NULL,
                    violation_count INTEGER DEFAULT 0,
                    violations_json TEXT DEFAULT '[]',
                    industry TEXT DEFAULT 'general',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id TEXT NOT NULL,
                    violation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    replacement TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_review(self, review_id, text, status, overall_risk,
                    violation_count, violations, industry="general"):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?)",
                (review_id, text, status, overall_risk, violation_count,
                 json.dumps(violations, ensure_ascii=False), industry,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def save_feedback(self, review_id, violation_id, action, replacement=None):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO feedback (review_id, violation_id, action, replacement, created_at) VALUES (?,?,?,?,?)",
                (review_id, violation_id, action, replacement,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def get_stats(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            total_reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            total_violations = conn.execute("SELECT COALESCE(SUM(violation_count),0) FROM reviews").fetchone()[0]
            rows = conn.execute("SELECT violations_json FROM reviews WHERE violation_count > 0").fetchall()
            category_counts = {}
            severity_counts = {"high": 0, "medium": 0, "low": 0, "pass": 0}
            for row in rows:
                for v in json.loads(row[0]):
                    cat = v.get("category", "未知")
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    sev = v.get("severity", "low")
                    if sev in severity_counts:
                        severity_counts[sev] += 1
            recent = conn.execute(
                "SELECT review_id, substr(text,1,30), status, overall_risk, violation_count "
                "FROM reviews ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            return {
                "total_reviews": total_reviews,
                "total_violations": total_violations,
                "violation_by_category": [{"category": k, "count": v} for k, v in category_counts.items()],
                "violation_by_severity": [{"severity": k, "count": v} for k, v in severity_counts.items()],
                "recent_reviews": [
                    {"reviewId": r[0], "text": r[1], "status": r[2],
                     "overallRisk": r[3], "violationCount": r[4]}
                    for r in recent
                ],
            }

    def close(self):
        pass
