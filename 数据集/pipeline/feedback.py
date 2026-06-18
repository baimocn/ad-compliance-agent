"""
广告法合规审查 Agent — 反馈记忆管线

用户驳回/修改 → 存储 → 影响后续检索的完整流程。

反馈类型:
  - accepted: 用户采纳了审查结果 → boost 该结果相关条文/案例
  - rejected: 用户驳回了审查结果 → 降权该结果
  - modified: 用户修改了建议 → 记录修改，适度降权原文

反馈存储结构:
  key:    feedback:<action>:<timestamp>:<target_key>
  source: "feedback"
  tags:   ["feedback", "<action>", "target:<target_key>", ...]
  value:  JSON 序列化的反馈详情
"""
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from config import SOURCE_LAW, SOURCE_CASE, SOURCE_INDUSTRY, KEY_PREFIX_FEEDBACK
from storage import VmemStore

logger = logging.getLogger(__name__)


# ============================================================
# 反馈数据结构
# ============================================================

class FeedbackAction(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


@dataclass
class FeedbackRecord:
    """单条反馈记录。"""
    action: FeedbackAction
    target_keys: list[str]          # 被影响的原始检索结果 key 列表
    query: str                      # 触发该反馈的原始查询
    original_text: str              # Agent 原始输出 (被用户看到的内容)
    user_comment: str = ""          # 用户的评论/修改意见
    modified_text: str = ""         # 用户修改后的文本 (modified 时)
    severity: str = "normal"        # normal / high / critical
    confidence: float = 0.8         # 反馈置信度 (0-1)
    metadata: dict = field(default_factory=dict)


# ============================================================
# 反馈管线
# ============================================================

class FeedbackPipeline:
    """
    反馈记忆管线。

    职责:
    1. 接收用户反馈 (accepted / rejected / modified)
    2. 存储反馈到 vmem (feedback: source)
    3. 更新被影响条目的 confidence 分数
    4. 后续检索时自动应用反馈信号
    """

    def __init__(self, store: VmemStore):
        self.store = store

    # ----------------------------------------------------------
    # 接收反馈
    # ----------------------------------------------------------

    def record_feedback(self, record: FeedbackRecord) -> list[str]:
        """
        存储一条反馈记录。

        为每个 target_key 创建一条反馈记录，
        使后续检索能精确命中。

        Args:
            record: 反馈记录

        Returns:
            list[str]: 创建的反馈 key 列表
        """
        created_keys = []
        ts = int(time.time() * 1000)

        for target_key in record.target_keys:
            fb_key = f"{KEY_PREFIX_FEEDBACK}:{record.action.value}:{ts}:{target_key}"

            # 构建反馈文本 (用于全文检索)
            fb_text = self._build_feedback_text(record, target_key)

            # 构建标签
            tags = [
                "feedback",
                record.action.value,
                f"target:{target_key}",
                f"query:{record.query[:50]}",
            ]
            if record.severity != "normal":
                tags.append(f"severity:{record.severity}")

            ok = self.store.store(
                key=fb_key,
                value=fb_text,
                source="feedback",
                tags=tags,
                confidence=record.confidence,
            )

            if ok:
                created_keys.append(fb_key)
                logger.info(f"Feedback stored: {fb_key}")
            else:
                logger.error(f"Feedback store failed: {fb_key}")

        # 更新被影响条目的 confidence
        self._update_target_confidence(record)

        return created_keys

    def record_accepted(self, query: str, target_keys: list[str],
                        original_text: str = "",
                        comment: str = "") -> list[str]:
        """便捷方法: 记录采纳反馈。"""
        return self.record_feedback(FeedbackRecord(
            action=FeedbackAction.ACCEPTED,
            target_keys=target_keys,
            query=query,
            original_text=original_text,
            user_comment=comment,
            confidence=0.9,
        ))

    def record_rejected(self, query: str, target_keys: list[str],
                        original_text: str = "",
                        reason: str = "",
                        severity: str = "high") -> list[str]:
        """便捷方法: 记录驳回反馈。"""
        return self.record_feedback(FeedbackRecord(
            action=FeedbackAction.REJECTED,
            target_keys=target_keys,
            query=query,
            original_text=original_text,
            user_comment=reason,
            severity=severity,
            confidence=0.95,
        ))

    def record_modified(self, query: str, target_keys: list[str],
                        original_text: str = "",
                        modified_text: str = "",
                        comment: str = "") -> list[str]:
        """便捷方法: 记录修改反馈。"""
        return self.record_feedback(FeedbackRecord(
            action=FeedbackAction.MODIFIED,
            target_keys=target_keys,
            query=query,
            original_text=original_text,
            modified_text=modified_text,
            user_comment=comment,
            confidence=0.85,
        ))

    # ----------------------------------------------------------
    # 更新 confidence
    # ----------------------------------------------------------

    def _update_target_confidence(self, record: FeedbackRecord):
        """
        根据反馈类型调整目标条目的 confidence 值。

        累积反馈效应:
        - accepted: confidence += 0.1 (上限 1.0)
        - rejected: confidence -= 0.3 (下限 0.1)
        - modified: confidence -= 0.15 (下限 0.1)
        """
        adj_map = {
            FeedbackAction.ACCEPTED: 0.1,
            FeedbackAction.REJECTED: -0.3,
            FeedbackAction.MODIFIED: -0.15,
        }
        adj = adj_map.get(record.action, 0)

        for target_key in record.target_keys:
            if target_key in self.store._storage:
                current = self.store._storage[target_key].get("confidence", 1.0)
                new_conf = max(0.1, min(1.0, current + adj))
                self.store._storage[target_key]["confidence"] = new_conf
                logger.info(
                    f"Confidence updated: {target_key} "
                    f"{current:.2f} -> {new_conf:.2f}"
                )

    # ----------------------------------------------------------
    # 反馈文本构建
    # ----------------------------------------------------------

    @staticmethod
    def _build_feedback_text(record: FeedbackRecord, target_key: str) -> str:
        """构建反馈的可检索文本。"""
        parts = [
            f"反馈类型: {record.action.value}",
            f"目标条目: {target_key}",
            f"原始查询: {record.query}",
        ]
        if record.user_comment:
            parts.append(f"用户评论: {record.user_comment}")
        if record.modified_text:
            parts.append(f"修改后文本: {record.modified_text}")
        if record.original_text:
            parts.append(f"原始文本: {record.original_text[:200]}")
        return "\n".join(parts)

    # ----------------------------------------------------------
    # 查询反馈历史
    # ----------------------------------------------------------

    def get_feedback_for_key(self, target_key: str) -> list[dict]:
        """查询某个条目的所有反馈记录。"""
        results = self.store.search_fusion(
            query=f"target:{target_key}",
            top_k=20,
            w_vec=0.0,
            w_fts=0.8,
            w_time=0.1,
            w_conf=0.1,
            source_filter=["feedback"],
            topic_filter=[f"target:{target_key}"],
        )
        return results

    def get_feedback_stats(self) -> dict:
        """统计反馈数据。"""
        stats = {
            "total_feedback": 0,
            "accepted": 0,
            "rejected": 0,
            "modified": 0,
            "affected_targets": set(),
        }
        for key, item in self.store._storage.items():
            if item.get("source") != "feedback":
                continue
            stats["total_feedback"] += 1
            tags = item.get("tags", [])
            if "accepted" in tags:
                stats["accepted"] += 1
            elif "rejected" in tags:
                stats["rejected"] += 1
            elif "modified" in tags:
                stats["modified"] += 1
            for tag in tags:
                if tag.startswith("target:"):
                    stats["affected_targets"].add(tag[7:])

        stats["affected_targets"] = len(stats["affected_targets"])
        return stats


# ============================================================
# 反馈驱动的审查质量追踪
# ============================================================

@dataclass
class ReviewQualityMetrics:
    """审查质量指标。"""
    total_reviews: int = 0
    acceptance_rate: float = 0.0    # 采纳率
    rejection_rate: float = 0.0     # 驳回率
    modification_rate: float = 0.0  # 修改率
    avg_confidence: float = 0.0     # 平均置信度
    weak_areas: list[str] = field(default_factory=list)  # 需要加强的领域


def compute_quality_metrics(store: VmemStore) -> ReviewQualityMetrics:
    """基于反馈记录计算审查质量指标。"""
    pipeline = FeedbackPipeline(store)
    stats = pipeline.get_feedback_stats()

    total = stats["total_feedback"]
    if total == 0:
        return ReviewQualityMetrics()

    metrics = ReviewQualityMetrics(
        total_reviews=total,
        acceptance_rate=stats["accepted"] / total,
        rejection_rate=stats["rejected"] / total,
        modification_rate=stats["modified"] / total,
    )

    # 计算平均 confidence
    confidences = [
        item.get("confidence", 1.0)
        for item in store._storage.values()
        if item.get("source") != "feedback"
    ]
    metrics.avg_confidence = (
        sum(confidences) / len(confidences) if confidences else 1.0
    )

    # 识别薄弱领域 (被驳回率最高的 source)
    rejection_by_source = {}
    for item in store._storage.values():
        if item.get("source") != "feedback":
            continue
        tags = item.get("tags", [])
        if "rejected" not in tags:
            continue
        # 从反馈文本中推断涉及的 source
        value = item.get("value", "")
        for src in [SOURCE_LAW, SOURCE_CASE, SOURCE_INDUSTRY]:
            if src in value:
                rejection_by_source[src] = rejection_by_source.get(src, 0) + 1

    metrics.weak_areas = sorted(
        rejection_by_source.keys(),
        key=lambda x: rejection_by_source[x],
        reverse=True,
    )

    return metrics
