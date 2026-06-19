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
                "totalReviews": total_reviews,
                "totalViolations": total_violations,
                "violationByCategory": [{"category": k, "count": v} for k, v in category_counts.items()],
                "violationBySeverity": [{"severity": k, "count": v} for k, v in severity_counts.items()],
                "recentReviews": [
                    {"reviewId": r[0], "text": r[1], "status": r[2],
                     "overallRisk": r[3], "violationCount": r[4]}
                    for r in recent
                ],
            }

    def list_reviews(self, limit: int = 20, offset: int = 0) -> dict:
        """分页获取审查历史。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            rows = conn.execute(
                "SELECT review_id, substr(text,1,100) as text_preview, status, "
                "overall_risk, violation_count, industry, created_at "
                "FROM reviews ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return {
                "reviews": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def get_review(self, review_id: str) -> Optional[dict]:
        """获取单条审查详情。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("violations_json"):
                data["violations"] = json.loads(data["violations_json"])
                del data["violations_json"]
            return data

    def get_feedback_stats(self) -> dict:
        """获取反馈统计信息。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row

            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            confirm_count = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE action = 'confirm'"
            ).fetchone()[0]
            modify_count = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE action = 'modify'"
            ).fetchone()[0]
            dismiss_count = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE action = 'dismiss'"
            ).fetchone()[0]

            # 按违规类型分组的反馈（从 violations_json 中提取 category）
            # 简化：按 review 统计
            category_rows = conn.execute("""
                SELECT 'total' as category, action, COUNT(*) as cnt
                FROM feedback
                GROUP BY action
            """).fetchall()

            # 按禁用词（violation_id 前部分标识）分组
            # 简化：用 violation_id 作为关键词标识
            word_rows = conn.execute("""
                SELECT violation_id,
                       SUM(CASE WHEN action = 'confirm' THEN 1 ELSE 0 END) as confirms,
                       SUM(CASE WHEN action = 'dismiss' THEN 1 ELSE 0 END) as dismisses,
                       SUM(CASE WHEN action = 'modify' THEN 1 ELSE 0 END) as modifies,
                       COUNT(*) as total
                FROM feedback
                GROUP BY violation_id
                ORDER BY total DESC
                LIMIT 20
            """).fetchall()

            # 置信度学习调整记录（模拟）
            learning_adjustments = []
            for wr in word_rows:
                wr_dict = dict(wr)
                total_f = wr_dict["total"]
                dismiss_rate = wr_dict["dismisses"] / total_f if total_f > 0 else 0
                confirm_rate = wr_dict["confirms"] / total_f if total_f > 0 else 0
                if total_f >= 3:  # 有足够反馈样本才调整
                    if dismiss_rate >= 0.7:
                        adjustment = f"置信度降低 {-0.15:.0%}（{wr_dict['dismisses']}/{total_f} 次被驳回）"
                        learning_adjustments.append({
                            "violation_id": wr_dict["violation_id"],
                            "adjustment": adjustment,
                            "direction": "down",
                            "magnitude": 0.15,
                            "sample_count": total_f,
                        })
                    elif confirm_rate >= 0.8:
                        adjustment = f"置信度提升 +{0.1:.0%}（{wr_dict['confirms']}/{total_f} 次被确认）"
                        learning_adjustments.append({
                            "violation_id": wr_dict["violation_id"],
                            "adjustment": adjustment,
                            "direction": "up",
                            "magnitude": 0.1,
                            "sample_count": total_f,
                        })

            return {
                "total_feedback": total,
                "confirm_count": confirm_count,
                "modify_count": modify_count,
                "dismiss_count": dismiss_count,
                "word_feedback": [dict(w) for w in word_rows],
                "category_feedback": [dict(c) for c in category_rows],
                "learning_adjustments": learning_adjustments,
            }

    def close(self):
        pass
