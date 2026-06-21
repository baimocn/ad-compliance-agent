"""
VmemStore — 纯 SQLite 降级实现（不依赖 sentence_transformers/vmem）
提供 store_item / search / batch_store / get_stats / close 接口
"""

import sys
from pathlib import Path
import sqlite3, os, json, re

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))


class FallbackStore:
    """纯 SQLite 关键词搜索降级实现（含 FTS5 + jieba 中文分词）"""
    def __init__(self, db_path, engine=None):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS items "
            "(key TEXT PRIMARY KEY, value TEXT, source TEXT, tags TEXT)"
        )
        # FTS5 虚拟表（trigram 支持中文）
        self._conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                key, value, source, tags,
                tokenize='trigram',
                content='items',
                content_rowid='rowid'
            );
            CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                INSERT INTO items_fts(rowid, key, value, source, tags)
                VALUES (new.rowid, new.key, new.value, new.source, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, key, value, source, tags)
                VALUES ('delete', old.rowid, old.key, old.value, old.source, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, key, value, source, tags)
                VALUES ('delete', old.rowid, old.key, old.value, old.source, old.tags);
                INSERT INTO items_fts(rowid, key, value, source, tags)
                VALUES (new.rowid, new.key, new.value, new.source, new.tags);
            END;
        """)
        self._conn.commit()
        # 重建 FTS5 索引（迁移已有数据）
        self._rebuild_fts()

    def _rebuild_fts(self):
        """重建 FTS5 索引（用于迁移旧数据）"""
        try:
            self._conn.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
            self._conn.commit()
        except Exception:
            pass

    def store(self, key, value, source, tags=""):
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO items VALUES (?,?,?,?)",
                (key, value, source, tags)
            )
            self._conn.commit()
            return True
        except Exception:
            return False

    def _expand_query(self, query: str) -> str:
        """对短查询进行扩写，改善中文召回"""
        expansions = {
            "第一": "第一 首先 领衔 冠军 首位 NO.1",
            "最佳": "最佳 最优 最好 极佳 绝佳",
            "最": "最 极 顶 超",
            "唯一": "唯一 独一 仅有 只此",
            "国家级": "国家级 国家 国字 全国",
        }
        for key, val in expansions.items():
            if key in query:
                return val
        return query

    def search_fusion(self, query="", query_emb=None, top_k=5,
                     w_vec=0.5, w_fts=0.2, w_time=0.1, w_conf=0.2,
                     topic_filter=None):
        """FTS5 关键词搜索（降级替代向量搜索）"""
        try:
            import jieba
            expanded = self._expand_query(query)
            tokens = " OR ".join(jieba.cut(expanded))
            rows = self._conn.execute(
                "SELECT i.key, i.value, i.source, i.tags, fts.rank "
                "FROM items_fts fts JOIN items i ON fts.rowid = i.rowid "
                "WHERE items_fts MATCH ? ORDER BY fts.rank LIMIT ?",
                (tokens, top_k * 3)
            ).fetchall()
            results = []
            for r in rows:
                results.append({
                    "key": r[0], "value": r[1], "source": r[2],
                    "tags": r[3], "score": -r[4],
                })
            if results:
                return results[:top_k]
        except Exception:
            pass

        # 兜底：LIKE 模糊搜索
        rows = self._conn.execute(
            "SELECT key, value, source, tags FROM items WHERE value LIKE ? LIMIT ?",
            (f"%{query}%", top_k * 3)
        ).fetchall()
        results = []
        for r in rows:
            results.append({
                "key": r[0], "value": r[1], "source": r[2], "tags": r[3], "score": 0.5
            })
        if not results:
            rows = self._conn.execute(
                "SELECT key, value, source, tags FROM items LIMIT ?", (top_k,)
            ).fetchall()
            for r in rows:
                results.append({
                    "key": r[0], "value": r[1], "source": r[2], "tags": r[3], "score": 0.3
                })
        return results[:top_k]

    def get_stats(self):
        total = self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        sources = {}
        for r in self._conn.execute("SELECT source, COUNT(*) FROM items GROUP BY source").fetchall():
            sources[r[0]] = r[1]
        return {"total": total, "sources": sources}

    def close(self):
        self._conn.close()


class EmbeddingEngine:
    """降级 EmbeddingEngine（不依赖 sentence_transformers）"""
    def __init__(self, model_path=None):
        pass

    def encode(self, texts):
        # 返回随机向量（降级模式，仅用于兼容接口）
        import random
        dim = 384
        return [[random.gauss(0, 1) for _ in range(dim)] for _ in texts]


# 尝试导入 vmem + torch，失败则用降级实现
_VMEM_AVAILABLE = False
try:
    import torch
    from vmem.store import MemoryVectorStore, EmbeddingEngine as VmemEmbeddingEngine
    EmbeddingEngine = VmemEmbeddingEngine
    _VMEM_AVAILABLE = True
    print("[storage] vmem 可用，使用向量搜索模式")
except ImportError as e:
    print(f"[storage] vmem 不可用（{e}），使用纯 SQLite 降级模式")


class VmemStore:
    def __init__(self, db_path: str, model_path: str = None):
        self._db_path = db_path
        # 始终初始化 FallbackStore 作为关键词搜索备份
        self._fallback = FallbackStore(db_path, None)
        if _VMEM_AVAILABLE:
            try:
                self._engine = EmbeddingEngine(model_path)
                self._store = MemoryVectorStore(db_path, self._engine)
                self._vmem_enabled = True
                print("[storage] vmem 可用，使用混合搜索模式（向量+关键词）")
            except Exception as e:
                print(f"[storage] vmem 初始化失败（{e}），仅使用关键词搜索")
                self._store = self._fallback
                self._vmem_enabled = False
        else:
            self._engine = EmbeddingEngine(model_path)
            self._store = self._fallback
            self._vmem_enabled = False

    def store_item(self, key, value, source, tags):
        # 同时写入两个存储
        r1 = self._store.store(key=key, value=value, source=source, tags=tags) if self._vmem_enabled else True
        r2 = self._fallback.store(key=key, value=value, source=source, tags=tags)
        return r1 or r2

    def search(self, query, top_k=5, source_filter=None):
        # 1. 先试 vmem 向量搜索
        vmem_results = []
        if self._vmem_enabled:
            try:
                query_emb = self._engine.encode([query])[0]
                fetch_k = top_k * 10 if source_filter else top_k
                vmem_results = self._store.search_fusion(
                    query=query, query_emb=query_emb, top_k=fetch_k,
                    w_vec=0.50, w_fts=0.20, w_time=0.10, w_conf=0.20,
                    topic_filter=None
                )
            except Exception as e:
                print(f"[vmem] search_fusion 失败: {e}")

        # 2. 再用 FallbackStore 做关键词搜索（能搜到 items 表中的数据）
        fallback_results = []
        try:
            fallback_results = self._fallback.search_fusion(query=query, top_k=top_k * 3)
        except Exception as e:
            print(f"[fallback] search_fusion 失败: {e}")

        # 3. 合并去重
        seen = set()
        merged = []
        for r in vmem_results + fallback_results:
            k = r.get("key", "")
            if k not in seen:
                seen.add(k)
                merged.append(r)

        if source_filter:
            merged = [r for r in merged if r.get("source") in source_filter]
        return merged[:top_k]

    def batch_store(self, items: list[dict]):
        count = 0
        for item in items:
            ok = self.store_item(
                key=item["key"], value=item["value"],
                source=item["source"], tags=item.get("tags", "")
            )
            if ok:
                count += 1
        return count

    def get_stats(self):
        # 合并两个存储的 stats
        s1 = self._store.get_stats() if self._vmem_enabled else {"total": 0, "sources": {}}
        s2 = self._fallback.get_stats()
        return {"vmem": s1, "fallback": s2}

    def close(self):
        try:
            self._store.close()
        except Exception:
            pass
        try:
            self._fallback.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 验证脚本：直接运行本文件时执行
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    tmp_db = os.path.join(tempfile.gettempdir(), "vmem_storage_test.db")
    print(f"[test] 使用临时数据库: {tmp_db}")

    store = VmemStore(db_path=tmp_db)

    # 1. 存储测试数据
    ok = store.store_item(
        key="test-hello",
        value="这是一条测试记忆，用于验证 VmemStore 的存储功能",
        source="test",
        tags="测试,验证"
    )
    print(f"[test] store_item 返回: {ok}")

    # 2. 搜索检索
    results = store.search(query="测试记忆", top_k=3)
    print(f"[test] search 返回 {len(results)} 条结果:")
    for r in results:
        print(f"  key={r['key']}  score={r.get('score',0):.4f}  value={r['value'][:60]}")

    # 3. 统计
    stats = store.get_stats()
    print(f"[test] stats: total={stats['total']}, sources={stats['sources']}")

    store.close()

    # 清理临时文件
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(tmp_db + suffix)
        except OSError:
            pass
    print("[test] 验证完成，临时文件已清理")
