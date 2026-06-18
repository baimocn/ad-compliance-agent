"""
VmemStore — vmem MemoryVectorStore 的简化封装
提供 store_item / search / batch_store / get_stats / close 接口
"""

import sys
sys.path.insert(0, 'D:/Desktop/黑客松')

from vmem.store import MemoryVectorStore, EmbeddingEngine


class VmemStore:
    def __init__(self, db_path: str, model_path: str = None):
        self._engine = EmbeddingEngine(model_path)
        self._store = MemoryVectorStore(db_path, self._engine)

    def store_item(self, key, value, source, tags):
        """存储一条知识"""
        return self._store.store(key=key, value=value, source=source, tags=tags)

    def search(self, query, top_k=5, source_filter=None):
        """融合搜索。当指定 source_filter 时，先扩大候选集再过滤，避免漏掉特定来源的结果。"""
        query_emb = self._engine.encode([query])[0]
        # 如果有来源过滤，扩大候选集以确保各来源都有机会入选
        fetch_k = top_k * 10 if source_filter else top_k
        results = self._store.search_fusion(
            query=query, query_emb=query_emb, top_k=fetch_k,
            w_vec=0.50, w_fts=0.20, w_time=0.10, w_conf=0.20,
            topic_filter=None
        )
        # 按 source_filter 过滤
        if source_filter:
            results = [r for r in results if r.get("source") in source_filter]
        return results[:top_k]

    def batch_store(self, items: list[dict]):
        """批量存储"""
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
        """获取统计信息"""
        return self._store.get_stats()

    def close(self):
        self._store.close()


# ---------------------------------------------------------------------------
# 验证脚本：直接运行本文件时执行
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile, os

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
        print(f"  key={r['key']}  score={r['score']:.4f}  value={r['value'][:60]}")

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
