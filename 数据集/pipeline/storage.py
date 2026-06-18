"""
广告法合规审查 Agent — 存储层

负责将解析后的 chunk 批量写入 vmem MemoryVectorStore。
提供:
  - store_chunks(): 批量入库
  - store_single(): 单条入库
  - get_store_stats(): 入库统计
  - rebuild_index(): 重建索引
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# vmem 适配层 — 封装实际 vmem API
# ============================================================

class VmemStore:
    """
    vmem MemoryVectorStore 的薄封装。

    实际使用时替换为真实的 vmem 客户端实例。
    接口说明:
      - store(key, value, source, tags, level, confidence)
      - search_fusion(query, query_emb, top_k, w_vec, w_fts, w_time, w_conf, topic_filter)
      - EmbeddingEngine.encode(texts) -> list[list[float]]
    """

    def __init__(self, embedding_engine=None):
        """
        Args:
            embedding_engine: 具有 encode(texts: list[str]) -> list[list[float]] 方法的对象
        """
        self.embedding_engine = embedding_engine
        self._storage: dict[str, dict] = {}  # 内存模拟存储 (hackathon demo)
        self._stats = {
            "total_stored": 0,
            "by_source": {},
            "last_store_time": None,
        }

    def store(self, key: str, value: str, source: str,
              tags: list[str] = None, level: str = "project",
              confidence: float = 1.0) -> bool:
        """
        存储单条记录到 vmem。

        Args:
            key: 唯一标识，格式为 "prefix:identifier"
            value: 正文内容 (用于 embedding 和全文检索)
            source: 子库标识 (ad_law / ad_case / ad_industry / ...)
            tags: 标签列表 (用于 topic_filter 过滤)
            level: 存储级别 (project/global)
            confidence: 置信度 (0-1，反馈记忆用)

        Returns:
            bool: 是否成功
        """
        try:
            self._storage[key] = {
                "key": key,
                "value": value,
                "source": source,
                "tags": tags or [],
                "level": level,
                "confidence": confidence,
                "stored_at": time.time(),
            }
            self._stats["total_stored"] += 1
            self._stats["by_source"][source] = \
                self._stats["by_source"].get(source, 0) + 1
            self._stats["last_store_time"] = time.time()
            return True
        except Exception as e:
            logger.error(f"存储失败 key={key}: {e}")
            return False

    def search_fusion(self, query: str, query_emb: list[float] = None,
                      top_k: int = 10, w_vec: float = 0.5, w_fts: float = 0.2,
                      w_time: float = 0.1, w_conf: float = 0.2,
                      topic_filter: list[str] = None,
                      source_filter: list[str] = None) -> list[dict]:
        """
        融合检索: 向量 + 全文 + 时间衰减 + 置信度。

        Args:
            query: 查询文本
            query_emb: 查询向量 (如果为 None，内部编码)
            top_k: 返回条数
            w_vec: 向量相似度权重
            w_fts: 全文检索权重
            w_time: 时间衰减权重
            w_conf: 置信度权重
            topic_filter: 按标签过滤 (AND 逻辑)
            source_filter: 按 source 过滤 (OR 逻辑)

        Returns:
            list[dict]: 按融合分数降序排列的结果
        """
        if query_emb is None and self.embedding_engine:
            query_emb = self.embedding_engine.encode([query])[0]

        results = []
        for key, item in self._storage.items():
            # source 过滤
            if source_filter and item["source"] not in source_filter:
                continue
            # topic 过滤 (AND: 所有 filter tag 都必须存在)
            if topic_filter:
                if not all(t in item["tags"] for t in topic_filter):
                    continue

            # 计算各路分数
            score_vec = self._compute_vector_score(query_emb, item["value"]) if query_emb else 0.0
            score_fts = self._compute_fts_score(query, item["value"])
            score_time = self._compute_time_score(item.get("stored_at", 0))
            score_conf = item.get("confidence", 1.0)

            # 加权融合
            total = (w_vec * score_vec +
                     w_fts * score_fts +
                     w_time * score_time +
                     w_conf * score_conf)

            results.append({
                "key": key,
                "value": item["value"],
                "source": item["source"],
                "tags": item["tags"],
                "score": total,
                "score_breakdown": {
                    "vec": score_vec,
                    "fts": score_fts,
                    "time": score_time,
                    "conf": score_conf,
                },
            })

        # 按分数降序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _compute_vector_score(self, query_emb: list[float], text: str) -> float:
        """计算向量相似度分数 (cosine similarity)。"""
        if not self.embedding_engine:
            return 0.5  # 无引擎时返回默认值
        doc_emb = self.embedding_engine.encode([text])[0]
        return self._cosine_similarity(query_emb, doc_emb)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度。"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _compute_fts_score(query: str, text: str) -> float:
        """简易全文检索分数 (关键词命中率)。"""
        query_chars = set(query.replace(" ", ""))
        if not query_chars:
            return 0.0
        hits = sum(1 for c in query_chars if c in text)
        return hits / len(query_chars)

    @staticmethod
    def _compute_time_score(stored_at: float) -> float:
        """时间衰减分数 (越新越高)。"""
        if stored_at == 0:
            return 0.5
        age_hours = (time.time() - stored_at) / 3600
        # 指数衰减，半衰期 720 小时 (30天)
        import math
        return math.exp(-0.693 * age_hours / 720)

    def delete(self, key: str) -> bool:
        """删除指定 key。"""
        if key in self._storage:
            source = self._storage[key]["source"]
            del self._storage[key]
            self._stats["total_stored"] -= 1
            self._stats["by_source"][source] = \
                self._stats["by_source"].get(source, 0) - 1
            return True
        return False

    def get_stats(self) -> dict:
        """返回存储统计信息。"""
        return dict(self._stats)

    def count(self) -> int:
        return len(self._storage)


# ============================================================
# 批量入库函数
# ============================================================

def store_chunks(store: VmemStore, chunks: list[dict],
                 batch_size: int = 32, embedding_engine=None) -> dict:
    """
    将解析后的 chunk 列表批量写入 vmem。

    Args:
        store: VmemStore 实例
        chunks: parsers 输出的 chunk 列表
        batch_size: embedding 批处理大小
        embedding_engine: 可选，单独传入的 embedding 引擎

    Returns:
        {
            "total": int,
            "success": int,
            "failed": int,
            "failed_keys": list[str],
        }
    """
    engine = embedding_engine or store.embedding_engine
    success = 0
    failed = 0
    failed_keys = []

    # 分批处理 embedding
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]

        # 批量编码 (如果有引擎的话)
        if engine:
            try:
                embeddings = engine.encode(texts)
            except Exception as e:
                logger.warning(f"Batch encoding failed, falling back: {e}")
                embeddings = None
        else:
            embeddings = None

        for j, chunk in enumerate(batch):
            ok = store.store(
                key=chunk["key"],
                value=chunk["text"],
                source=chunk["source"],
                tags=chunk["tags"],
            )
            if ok:
                success += 1
            else:
                failed += 1
                failed_keys.append(chunk["key"])

    return {
        "total": len(chunks),
        "success": success,
        "failed": failed,
        "failed_keys": failed_keys,
    }


def store_all_parsed(store: VmemStore, all_chunks: dict[str, list[dict]],
                     embedding_engine=None) -> dict:
    """
    入库所有解析结果。

    Args:
        store: VmemStore 实例
        all_chunks: parsers.parse_all() 的返回值
        embedding_engine: 可选 embedding 引擎

    Returns:
        按子库分组的入库结果统计
    """
    results = {}
    for lib_name, chunks in all_chunks.items():
        if not chunks:
            results[lib_name] = {"total": 0, "success": 0, "failed": 0}
            continue
        result = store_chunks(store, chunks, embedding_engine=embedding_engine)
        results[lib_name] = result
        logger.info(f"[{lib_name}] 入库完成: {result['success']}/{result['total']}")
    return results


# ============================================================
# 重建索引
# ============================================================

def rebuild_index(store: VmemStore, all_chunks: dict[str, list[dict]],
                  embedding_engine=None) -> dict:
    """
    清空并重建整个知识库索引。

    ⚠️ 会删除所有已有数据。
    """
    # 清空
    keys_to_delete = list(store._storage.keys())
    for key in keys_to_delete:
        store.delete(key)
    logger.info(f"已清空 {len(keys_to_delete)} 条旧数据")

    # 重建
    return store_all_parsed(store, all_chunks, embedding_engine)
