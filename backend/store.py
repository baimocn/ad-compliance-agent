"""
审查记录、用户账户、计费与反馈存储 — SQLite（合并版）
"""
import sqlite3
import json
import time
import bcrypt
import secrets
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
            # 用户表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # 审查记录表（含 user_id 字段）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    overall_risk TEXT NOT NULL,
                    violation_count INTEGER DEFAULT 0,
                    violations_json TEXT DEFAULT '[]',
                    industry TEXT DEFAULT 'general',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            # 反馈表
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
            # Token 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reset_token TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            # 迁移：如果 reviews 表没有 user_id 字段，加上它
            cols = [r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()]
            if 'user_id' not in cols:
                conn.execute("ALTER TABLE reviews ADD COLUMN user_id INTEGER")
            conn.commit()
        self._init_billing()

    # ================================================================
    # 用户管理
    # ================================================================

    def create_user(self, username: str, password: str) -> dict:
        """注册用户，返回 {success, error, user_id}"""
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            with sqlite3.connect(self._db_path) as conn:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                    (username, password_hash, time.strftime("%Y-%m-%dT%H:%M:%SZ"))
                )
                conn.commit()
                return {"success": True, "user_id": cur.lastrowid}
        except sqlite3.IntegrityError:
            return {"success": False, "error": "用户名已存在"}

    def verify_user(self, username: str, password: str) -> dict:
        """验证登录，返回 {success, user_id, username}"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username=?", (username,)
            ).fetchone()
        if row:
            stored_hash = row[2]
            try:
                if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                    return {"success": True, "user_id": row[0], "username": row[1]}
            except Exception:
                pass
            # 兼容旧版 SHA256 哈希
            import hashlib
            if hashlib.sha256(password.encode()).hexdigest() == stored_hash:
                new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, row[0]))
                    conn.commit()
                return {"success": True, "user_id": row[0], "username": row[1]}
        return {"success": False, "error": "用户名或密码错误"}

    def create_token(self, user_id: int) -> str:
        token = secrets.token_hex(32)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tokens (token, user_id, created_at) VALUES (?,?,?)",
                (token, user_id, time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()
        return token

    def get_user_by_token(self, token: str) -> Optional[dict]:
        """通过 token 获取用户信息，失败返回 None"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            t = conn.execute(
                "SELECT user_id FROM tokens WHERE token=?", (token,)
            ).fetchone()
            if not t:
                return None
            u = conn.execute(
                "SELECT id, username FROM users WHERE id=?", (t["user_id"],)
            ).fetchone()
            if not u:
                return None
            return {"user_id": u["id"], "username": u["username"]}

    # ---------- 密码重置 ----------

    def create_password_reset(self, username: str) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                return {"success": False, "error": "用户名不存在"}
            reset_token = secrets.token_hex(16)
            expiry = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(time.time() + 3600))
            conn.execute("DELETE FROM password_resets WHERE user_id=?", (row[0],))
            conn.execute(
                "INSERT INTO password_resets (user_id, reset_token, expiry) VALUES (?,?,?)",
                (row[0], reset_token, expiry)
            )
            conn.commit()
        return {"success": True, "reset_token": reset_token}

    def reset_password(self, username: str, reset_token: str, new_password: str) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                return {"success": False, "error": "用户名不存在"}
            pr = conn.execute(
                "SELECT reset_token, expiry FROM password_resets WHERE user_id=?",
                (row[0],)
            ).fetchone()
            if not pr or pr[0] != reset_token:
                return {"success": False, "error": "重置令牌无效"}
            if pr[1] < time.strftime("%Y-%m-%dT%H:%M:%SZ"):
                return {"success": False, "error": "重置令牌已过期"}
            password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, row[0]))
            conn.execute("DELETE FROM password_resets WHERE user_id=?", (row[0],))
            conn.commit()
        return {"success": True}

    # ---------- 注销账户 ----------

    def get_user_review_ids(self, user_id: int) -> list:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT review_id FROM reviews WHERE user_id=?", (user_id,)).fetchall()
            return [r[0] for r in rows]

    def delete_account(self, user_id: int) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            review_ids = [r[0] for r in conn.execute("SELECT review_id FROM reviews WHERE user_id=?", (user_id,)).fetchall()]
            for rid in review_ids:
                conn.execute("DELETE FROM feedback WHERE review_id=?", (rid,))
            conn.execute("DELETE FROM tokens WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM reviews WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM user_plans WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM usage_log WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM password_resets WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
        return {"success": True}

    # ================================================================
    # 审查记录
    # ================================================================

    def save_review(self, review_id, text, status, overall_risk,
                    violation_count, violations, industry="general", user_id=None):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reviews "
                "(review_id, user_id, text, status, overall_risk, violation_count, "
                "violations_json, industry, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (review_id, user_id, text, status, overall_risk, violation_count,
                 json.dumps(violations, ensure_ascii=False), industry,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def get_user_reviews(self, user_id: int, limit: int = 50, risk: str = None,
                          query: str = None, date_from: str = None, date_to: str = None) -> list:
        """获取某用户的历史审查记录，支持筛选"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = ("SELECT review_id, text, status, overall_risk, "
                   "violation_count, created_at FROM reviews WHERE user_id=?")
            params = [user_id]
            if risk and risk != "all":
                sql += " AND overall_risk=?"
                params.append(risk)
            if query:
                sql += " AND text LIKE ?"
                params.append(f"%{query}%")
            if date_from:
                sql += " AND created_at >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND created_at <= ?"
                params.append(date_to)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["text_preview"] = (r["text"] or "")[:50]
                results.append(d)
            return results

    def save_feedback(self, review_id, violation_id, action, replacement=None):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO feedback (review_id, violation_id, action, replacement, created_at) VALUES (?,?,?,?,?)",
                (review_id, violation_id, action, replacement,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def get_stats(self, user_id: int = None):
        """统计信息；传 user_id 则只统计该用户"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            where = "WHERE user_id=?" if user_id else ""
            params = (user_id,) if user_id else ()
            total_reviews = conn.execute(f"SELECT COUNT(*) FROM reviews {where}", params).fetchone()[0]
            total_violations = conn.execute(
                f"SELECT COALESCE(SUM(violation_count),0) FROM reviews {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT violations_json FROM reviews WHERE violation_count > 0 {'AND user_id=?' if user_id else ''}",
                params
            ).fetchall()
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
                f"SELECT review_id, substr(text,1,30), status, overall_risk, violation_count "
                f"FROM reviews {'WHERE user_id=?' if user_id else ''} ORDER BY created_at DESC LIMIT 10",
                params
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

    # ================================================================
    # 审查历史（分页）— 来自队友版本
    # ================================================================

    def list_reviews(self, limit: int = 20, offset: int = 0) -> dict:
        """分页获取审查历史（全量，不区分用户）"""
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
        """获取单条审查详情"""
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

    # ================================================================
    # 反馈统计 — 来自队友版本
    # ================================================================

    def get_feedback_stats(self) -> dict:
        """获取反馈统计信息"""
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

            category_rows = conn.execute("""
                SELECT 'total' as category, action, COUNT(*) as cnt
                FROM feedback GROUP BY action
            """).fetchall()

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

            learning_adjustments = []
            for wr in word_rows:
                wr_dict = dict(wr)
                total_f = wr_dict["total"]
                dismiss_rate = wr_dict["dismisses"] / total_f if total_f > 0 else 0
                confirm_rate = wr_dict["confirms"] / total_f if total_f > 0 else 0
                if total_f >= 3:
                    if dismiss_rate >= 0.7:
                        learning_adjustments.append({
                            "violation_id": wr_dict["violation_id"],
                            "adjustment": f"置信度降低 {-0.15:.0%}（{wr_dict['dismisses']}/{total_f} 次被驳回）",
                            "direction": "down",
                            "magnitude": 0.15,
                            "sample_count": total_f,
                        })
                    elif confirm_rate >= 0.8:
                        learning_adjustments.append({
                            "violation_id": wr_dict["violation_id"],
                            "adjustment": f"置信度提升 +{0.1:.0%}（{wr_dict['confirms']}/{total_f} 次被确认）",
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

    # ================================================================
    # 计费与套餐
    # ================================================================

    DEFAULT_PLANS = [
        {"id": "free", "name": "免费版", "price": 0, "max_reviews": 20, "max_batch": 1, "max_batch_lines": 10, "features": "基础规则检测"},
        {"id": "pro", "name": "专业版", "price": 29, "max_reviews": 500, "max_batch": 20, "max_batch_lines": 100, "features": "全部功能+报告导出"},
        {"id": "enterprise", "name": "企业版", "price": 99, "max_reviews": -1, "max_batch": -1, "max_batch_lines": 100, "features": "不限次数+优先支持"},
    ]

    def _init_billing(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    max_reviews INTEGER NOT NULL,
                    max_batch INTEGER NOT NULL,
                    max_batch_lines INTEGER NOT NULL,
                    features TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_plans (
                    user_id INTEGER PRIMARY KEY,
                    plan_id TEXT NOT NULL DEFAULT 'free',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    review_count INTEGER DEFAULT 0,
                    batch_count INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            existing = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
            if existing == 0:
                for p in self.DEFAULT_PLANS:
                    conn.execute(
                        "INSERT INTO plans (id, name, price, max_reviews, max_batch, max_batch_lines, features) VALUES (?,?,?,?,?,?,?)",
                        (p["id"], p["name"], p["price"], p["max_reviews"], p["max_batch"], p["max_batch_lines"], p["features"])
                    )
            conn.commit()

    def get_plans(self) -> list:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM plans ORDER BY price").fetchall()
            return [dict(r) for r in rows]

    def get_user_plan(self, user_id: int) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT p.*, up.start_date, up.end_date, up.status "
                "FROM user_plans up JOIN plans p ON up.plan_id = p.id "
                "WHERE up.user_id=?", (user_id,)
            ).fetchone()
            if row:
                return dict(row)
            return dict(self.DEFAULT_PLANS[0])

    def ensure_user_plan(self, user_id: int):
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT 1 FROM user_plans WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "INSERT INTO user_plans (user_id, plan_id, start_date, status) VALUES (?,?,?,?)",
                    (user_id, "free", now, "active")
                )
                conn.commit()

    def upgrade_plan(self, user_id: int, plan_id: str) -> dict:
        plans = {p["id"]: p for p in self.DEFAULT_PLANS}
        if plan_id not in plans:
            return {"success": False, "error": "套餐不存在"}
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_plans (user_id, plan_id, start_date, status) VALUES (?,?,?,?)",
                (user_id, plan_id, now, "active")
            )
            conn.commit()
        return {"success": True, "plan": plans[plan_id]}

    def check_usage_limit(self, user_id: int) -> dict:
        plan = self.get_user_plan(user_id)
        today = time.strftime("%Y-%m-%d")
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(review_count),0), COALESCE(SUM(batch_count),0) "
                "FROM usage_log WHERE user_id=? AND date=?", (user_id, today)
            ).fetchone()
        reviews_today = row[0]
        batches_today = row[1]
        max_reviews = plan["max_reviews"]
        max_batch = plan["max_batch"]
        if max_reviews != -1 and reviews_today >= max_reviews:
            return {"allowed": False, "reason": f"今日审查次数已达上限 ({max_reviews}次)"}
        if max_batch != -1 and batches_today >= max_batch:
            return {"allowed": False, "reason": f"今日批量审查次数已达上限 ({max_batch}次)"}
        return {"allowed": True, "reason": ""}

    def log_usage(self, user_id: int, review_count: int = 1, batch_count: int = 0, tokens: int = 0):
        today = time.strftime("%Y-%m-%d")
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT id, review_count, batch_count, total_tokens FROM usage_log WHERE user_id=? AND date=?",
                (user_id, today)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE usage_log SET review_count=?, batch_count=?, total_tokens=? WHERE id=?",
                    (existing[1] + review_count, existing[2] + batch_count, existing[3] + tokens, existing[0])
                )
            else:
                conn.execute(
                    "INSERT INTO usage_log (user_id, date, review_count, batch_count, total_tokens) VALUES (?,?,?,?,?)",
                    (user_id, today, review_count, batch_count, tokens)
                )
            conn.commit()

    def get_usage_stats(self, user_id: int) -> dict:
        plan = self.get_user_plan(user_id)
        today = time.strftime("%Y-%m-%d")
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(review_count),0), COALESCE(SUM(batch_count),0), "
                "COALESCE(SUM(total_tokens),0) FROM usage_log WHERE user_id=? AND date=?",
                (user_id, today)
            ).fetchone()
            month_rows = conn.execute(
                "SELECT COALESCE(SUM(review_count),0), COALESCE(SUM(batch_count),0), "
                "COALESCE(SUM(total_tokens),0) FROM usage_log WHERE user_id=? "
                "AND date >= date('now','start of month')", (user_id,)
            ).fetchone()
        return {
            "plan": plan,
            "today": {"reviews": row[0], "batches": row[1], "tokens": row[2]},
            "thisMonth": {"reviews": month_rows[0], "batches": month_rows[1], "tokens": month_rows[2]},
            "limits": {
                "maxReviews": plan["max_reviews"],
                "maxBatch": plan["max_batch"],
            }
        }

    def close(self):
        pass
