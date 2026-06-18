"""
广告法合规审查 Agent — 检索层

三库并行检索 + 融合排序:
  1. 对用户输入做意图分类 (判断查什么)
  2. 三库并行调用 search_fusion (各自 source_filter)
  3. 子库权重 boost + RRF 融合
  4. 上下文组装 (返回给 LLM 的 prompt 片段)
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import (
    SOURCE_LAW, SOURCE_CASE, SOURCE_INDUSTRY,
    SOURCE_BANNED, SOURCE_REPLACE,
    RetrievalConfig,
)
from storage import VmemStore

logger = logging.getLogger(__name__)


# ============================================================
# 查询意图分类
# ============================================================

class QueryRouter:
    """
    根据查询文本判断应该检索哪些子库。
    简单规则引擎 + 关键词匹配 (hackathon 版本)。
    """

    # 关键词→子库映射
    KEYWORD_MAP = {
        SOURCE_LAW: [
            "法律", "条文", "规定", "法规", "广告法", "条款", "释义",
            "管理办法", "处罚依据", "法条", "第九条", "第四条", "第二十八条",
            "第五十七条", "第五十五条",
        ],
        SOURCE_CASE: [
            "案例", "处罚", "罚款", "被罚", "判决", "处罚结果",
            "处罚案例", "类似案例", "过往案例", "罚了多少",
        ],
        SOURCE_INDUSTRY: [
            "行业", "食品", "化妆品", "教育", "金融", "房地产",
            "医疗", "酒类", "禁区", "行业规则", "行业规定",
        ],
        SOURCE_BANNED: [
            "禁用词", "违禁词", "敏感词", "不能用", "哪些词",
            "极限用语", "绝对化", "虚假宣传",
        ],
        SOURCE_REPLACE: [
            "替代", "替换", "怎么改", "合规表述", "合规说法",
            "可以用什么", "换什么",
        ],
    }

    def route(self, query: str) -> dict[str, float]:
        """
        返回各子库的检索权重。

        Returns:
            {source_name: weight, ...}  权重 0-1
        """
        weights = {}
        query_lower = query.lower()

        for source, keywords in self.KEYWORD_MAP.items():
            hit_count = sum(1 for kw in keywords if kw in query_lower)
            if hit_count > 0:
                weights[source] = min(1.0, 0.3 + hit_count * 0.15)
            else:
                weights[source] = 0.1  # 保留最低权重，确保不完全排除

        # 如果没有任何关键词命中，默认全开
        if not weights:
            weights = {
                SOURCE_LAW: 0.3,
                SOURCE_CASE: 0.3,
                SOURCE_INDUSTRY: 0.2,
                SOURCE_BANNED: 0.1,
                SOURCE_REPLACE: 0.1,
            }

        return weights

    def classify_intent(self, query: str) -> str:
        """粗粒度意图分类。"""
        weights = self.route(query)
        return max(weights, key=weights.get)


# ============================================================
# 三库并行检索器
# ============================================================

@dataclass
class RetrievalResult:
    """单条检索结果。"""
    key: str
    text: str
    source: str
    tags: list[str]
    score: float
    score_breakdown: dict = field(default_factory=dict)
    rank: int = 0
    source_lib: str = ""


@dataclass
class FusionRetrievalResult:
    """融合检索的完整结果。"""
    query: str
    results: list[RetrievalResult]
    per_lib_results: dict[str, list[RetrievalResult]]
    intent_weights: dict[str, float]
    total_candidates: int = 0


class ThreeLibRetriever:
    """
    三库并行检索器。

    流程:
    1. query_router 判断意图 → 各库权重
    2. 三库并行调用 store.search_fusion (各自 source_filter)
    3. 对各库结果应用权重 boost
    4. RRF (Reciprocal Rank Fusion) 合并排序
    5. 截取 top_k
    """

    def __init__(self, store: VmemStore, config: RetrievalConfig = None,
                 embedding_engine=None):
        self.store = store
        self.config = config or RetrievalConfig()
        self.router = QueryRouter()
        self.embedding_engine = embedding_engine or store.embedding_engine

    def retrieve(self, query: str, top_k: int = None,
                 include_feedback: bool = True) -> FusionRetrievalResult:
        """
        主检索入口。

        Args:
            query: 用户查询文本
            top_k: 返回条数 (默认用 config)
            include_feedback: 是否包含反馈记忆

        Returns:
            FusionRetrievalResult
        """
        top_k = top_k or self.config.top_k

        # Step 1: 意图路由
        intent_weights = self.router.route(query)
        logger.info(f"Intent weights: {intent_weights}")

        # Step 2: 编码查询
        query_emb = None
        if self.embedding_engine:
            try:
                query_emb = self.embedding_engine.encode([query])[0]
            except Exception as e:
                logger.warning(f"Query encoding failed: {e}")

        # Step 3: 三库并行检索
        per_lib_results = {}
        for source, weight in intent_weights.items():
            if weight < 0.05:
                continue  # 跳过权重极低的库

            results = self.store.search_fusion(
                query=query,
                query_emb=query_emb,
                top_k=top_k * 2,  # 多取一些用于融合
                w_vec=self.config.w_vec,
                w_fts=self.config.w_fts,
                w_time=self.config.w_time,
                w_conf=self.config.w_conf,
                source_filter=[source],
            )

            # 应用子库权重 boost
            for r in results:
                r["score"] *= weight

            per_lib_results[source] = results

        # Step 4: RRF 融合
        merged = self._rrf_merge(per_lib_results, top_k * 2)

        # Step 5: 反馈记忆 boost
        if include_feedback:
            merged = self._apply_feedback_boost(merged, query)

        # Step 6: 截取 top_k
        merged = merged[:top_k]

        # 构建结果对象
        result_objs = []
        for i, item in enumerate(merged):
            obj = RetrievalResult(
                key=item["key"],
                text=item["value"],
                source=item["source"],
                tags=item.get("tags", []),
                score=item["score"],
                score_breakdown=item.get("score_breakdown", {}),
                rank=i + 1,
                source_lib=item["source"],
            )
            result_objs.append(obj)

        total_candidates = sum(len(v) for v in per_lib_results.values())

        return FusionRetrievalResult(
            query=query,
            results=result_objs,
            per_lib_results={
                k: [self._to_result(r) for r in v]
                for k, v in per_lib_results.items()
            },
            intent_weights=intent_weights,
            total_candidates=total_candidates,
        )

    def _rrf_merge(self, per_lib_results: dict[str, list[dict]],
                   top_k: int, k: int = 60) -> list[dict]:
        """
        Reciprocal Rank Fusion 合并多路结果。

        RRF score = sum(1 / (k + rank_i)) per result across all lists.

        Args:
            per_lib_results: {source: [results]}
            top_k: 最终返回数
            k: RRF 常数 (默认 60)
        """
        # 收集所有 key 及其在各列表中的排名
        key_scores: dict[str, dict] = {}  # key -> {score, item}

        for source, results in per_lib_results.items():
            for rank, item in enumerate(results):
                key = item["key"]
                if key not in key_scores:
                    key_scores[key] = {
                        "item": item,
                        "rrf_score": 0.0,
                        "appearances": 0,
                    }
                # RRF: 原始分数加权 + 排名融合
                key_scores[key]["rrf_score"] += 1.0 / (k + rank + 1)
                key_scores[key]["appearances"] += 1
                # 保留最高原始分数对应的信息
                if item["score"] > key_scores[key]["item"]["score"]:
                    key_scores[key]["item"] = item

        # 组合最终分数 = RRF 分数 + 归一化后的原始分数
        for key, data in key_scores.items():
            data["final_score"] = (
                data["rrf_score"] * 0.6 +
                data["item"]["score"] * 0.4
            )

        # 排序
        sorted_items = sorted(
            key_scores.values(),
            key=lambda x: x["final_score"],
            reverse=True,
        )

        result = []
        for data in sorted_items[:top_k]:
            item = dict(data["item"])
            item["score"] = data["final_score"]
            item["rrf_score"] = data["rrf_score"]
            item["appearances"] = data["appearances"]
            result.append(item)

        return result

    def _apply_feedback_boost(self, results: list[dict],
                              query: str) -> list[dict]:
        """
        应用反馈记忆 boost:
        - 如果某个条文/案例之前被用户驳回过 → 降权
        - 如果某个条文/案例之前被用户采纳过 → 升权

        反馈记录存储在 feedback: 前缀下。
        """
        # 检索反馈记忆
        feedback_results = self.store.search_fusion(
            query=f"feedback:{query}",
            top_k=50,
            w_vec=0.3,
            w_fts=0.5,
            w_time=0.1,
            w_conf=0.1,
            source_filter=["feedback"],
        )

        # 构建 feedback 映射: target_key -> feedback_info
        feedback_map = {}
        for fb in feedback_results:
            tags = fb.get("tags", [])
            for tag in tags:
                if tag.startswith("target:"):
                    target_key = tag[7:]
                    feedback_map[target_key] = {
                        "action": fb.get("tags", []),
                        "score_adj": fb["score"],
                    }

        # 应用调整
        for result in results:
            key = result["key"]
            if key in feedback_map:
                fb = feedback_map[key]
                tags = fb["action"]
                if "rejected" in tags:
                    result["score"] *= 0.3  # 驳回过的大幅降权
                elif "accepted" in tags:
                    result["score"] *= 1.5  # 采纳过的升权
                elif "modified" in tags:
                    result["score"] *= 0.5  # 修改过的适度降权

        # 重新排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def _to_result(item: dict) -> RetrievalResult:
        return RetrievalResult(
            key=item["key"],
            text=item["value"],
            source=item["source"],
            tags=item.get("tags", []),
            score=item["score"],
        )


# ============================================================
# 上下文组装 (Prompt 片段生成)
# ============================================================

def build_retrieval_context(result: FusionRetrievalResult,
                            max_chars: int = 6000) -> str:
    """
    将检索结果组装为 LLM prompt 的上下文片段。

    Args:
        result: 融合检索结果
        max_chars: 上下文最大字符数

    Returns:
        格式化的上下文字符串，可直接注入 prompt
    """
    sections = {
        SOURCE_LAW: [],
        SOURCE_CASE: [],
        SOURCE_INDUSTRY: [],
        SOURCE_BANNED: [],
        SOURCE_REPLACE: [],
    }

    for r in result.results:
        if r.source in sections:
            sections[r.source].append(r)

    context_parts = []
    total_chars = 0

    # 法规条文 (最优先)
    if sections[SOURCE_LAW]:
        part = "## 相关法规条文\n\n"
        for r in sections[SOURCE_LAW]:
            entry = f"### [{r.key}]\n{r.text}\n\n"
            if total_chars + len(entry) + len(part) > max_chars:
                break
            part += entry
            total_chars += len(entry)
        context_parts.append(part)

    # 行业规则
    if sections[SOURCE_INDUSTRY]:
        part = "## 行业广告禁区规则\n\n"
        for r in sections[SOURCE_INDUSTRY]:
            entry = f"### [{r.tags[1] if len(r.tags) > 1 else r.key}]\n{r.text}\n\n"
            if total_chars + len(entry) + len(part) > max_chars:
                break
            part += entry
            total_chars += len(entry)
        context_parts.append(part)

    # 处罚案例
    if sections[SOURCE_CASE]:
        part = "## 相关处罚案例\n\n"
        for r in sections[SOURCE_CASE]:
            entry = f"{r.text}\n\n"
            if total_chars + len(entry) + len(part) > max_chars:
                break
            part += entry
            total_chars += len(entry)
        context_parts.append(part)

    # 禁用词 (作为参考)
    if sections[SOURCE_BANNED]:
        part = "## 禁用词参考\n\n"
        for r in sections[SOURCE_BANNED]:
            entry = f"{r.text}\n\n"
            if total_chars + len(entry) + len(part) > max_chars:
                break
            part += entry
            total_chars += len(entry)
        context_parts.append(part)

    # 替代映射
    if sections[SOURCE_REPLACE]:
        part = "## 合规替代建议\n\n"
        for r in sections[SOURCE_REPLACE]:
            entry = f"{r.text}\n\n"
            if total_chars + len(entry) + len(part) > max_chars:
                break
            part += entry
            total_chars += len(entry)
        context_parts.append(part)

    return "\n---\n\n".join(context_parts)


# ============================================================
# 便捷封装
# ============================================================

def search_ad_compliance(store: VmemStore, query: str,
                         top_k: int = 10,
                         embedding_engine=None) -> str:
    """
    一步完成: 查询 → 检索 → 上下文组装。

    Args:
        store: VmemStore
        query: 用户查询
        top_k: 返回条数
        embedding_engine: embedding 引擎

    Returns:
        可直接注入 prompt 的上下文字符串
    """
    retriever = ThreeLibRetriever(
        store=store,
        embedding_engine=embedding_engine,
    )
    result = retriever.retrieve(query, top_k=top_k)
    return build_retrieval_context(result)
