"""
ThreeLibRetriever — 三库并行检索器
分别检索 law / case / rule 三个子库，合并、去重后返回 top 结果。
支持查询类型自动识别与自适应融合权重。
"""

import re
from storage import VmemStore


# ============================================================
# QueryClassifier — 查询类型分类器
# ============================================================

class QueryClassifier:
    """基于加权关键词规则的查询类型分类器。

    使用三级加权关键词匹配：高权重(3) / 中权重(2) / 低权重(1)。
    当最高得分低于阈值时返回 general。

    分类结果：
        - law    : 法规条文类查询（如"第X条规定"、"绝对化用语定义"、"罚款标准"）
        - case   : 处罚案例类查询（如"某公司被罚"、"典型案例"、"处罚金额"）
        - rule   : 行业规则类查询（如"抖音规则"、"小红书要求"、"行业合规"）
        - general: 综合查询（同时检索三库，使用默认权重）
    """

    # ── 法规条文类 ──
    LAW_HIGH = [  # 高权重(3)：强信号
        r"第.条", r"第.*条规定", r"第几条", r"哪一条",
        r"广告法", r"法律规定", r"法律条文", r"法条",
        r"释义", r"法律责任", r"法律后果",
        r"如何认定", r"认定标准", r"构成要件",
        r"算不算违规", r"算不算违法", r"违不违规", r"合不合法",
        r"绝对化用语", r"极限用语", r"虚假广告的认定",
        r"违反了.*规定",
    ]
    LAW_MID = [  # 中权重(2)：中信号
        r"定义", r"概念", r"什么是", r"标准", r"规定",
        r"罚款标准", r"处罚标准",
        r"能否", r"是否违法", r"违法吗", r"可以吗", r"允许吗",
        r"能不能", r"可以宣传", r"能不能宣传",
        r"禁止", r"不得", r"合法吗",
        r"未成年人.*代言", r"代言.*规定",
        r"治疗功效", r"疾病预防", r"疾病.*治疗",
    ]
    LAW_LOW = [  # 低权重(1)：弱信号
        r"罚款", r"处罚", r"法律", r"违规",
        r"最高级", r"最佳", r"国家级", r"最低价",
        r"虚假宣传", r"虚假广告",
        r"代言", r"广告内容",
    ]

    # ── 处罚案例类 ──
    CASE_HIGH = [  # 高权重(3)：强信号
        r"案例", r"被罚了多少", r"被罚案例", r"处罚案例",
        r"典型案例", r"真实案例", r"实际案例", r"案例分析",
        r"案例有哪些", r"哪些案例",
        r"罚了多少", r"罚多少钱", r"罚款金额", r"处罚金额",
        r"被罚款", r"处罚决定",
    ]
    CASE_MID = [  # 中权重(2)：中信号
        r"被罚", r"某公司", r"某某公司", r"违法案例",
        r"判了", r"判决", r"举例", r"罚款多少",
        r"被处罚", r"行政处罚",
        r"怎么处罚", r"如何处罚", r"处罚方式",
        r"会被罚吗", r"怎么罚", r"会怎么处罚",
        r"代言.*处罚", r"虚假广告.*处罚",
    ]
    CASE_LOW = [  # 低权重(1)：弱信号
        r"罚款案例",
    ]

    # ── 行业规则类 ──
    RULE_HIGH = [  # 高权重(3)：强信号
        r"抖音", r"小红书", r"平台规则", r"审核规则",
        r"种草笔记", r"直播带货",
        r"行业规则", r"行业合规", r"合规要求",
        r"平台审核", r"平台要求",
    ]
    RULE_MID = [  # 中权重(2)：中信号
        r"化妆品广告", r"食品广告", r"医疗广告", r"医美广告",
        r"医疗美容广告", r"医疗美容",
        r"房地产广告", r"金融广告", r"教育广告",
        r"直播.*合规", r"合规.*要求",
        r"发布规范", r"怎么发布", r"如何发布",
        r"注意事项", r"注意什么", r"避坑", r"雷区",
        r"话术", r"规范",
        r"哪些禁止", r"禁止内容",
    ]
    RULE_LOW = [  # 低权重(1)：弱信号
        r"平台", r"要求", r"标注", r"能不能用", r"可以使用",
        r"直播间",
    ]

    # 得分低于此阈值则判定为 general
    GENERAL_THRESHOLD = 2

    @classmethod
    def classify(cls, query: str) -> str:
        """根据查询文本判断查询类型。

        Args:
            query: 查询文本

        Returns:
            查询类型：law / case / rule / general
        """
        q = query.strip()

        law_score = (
            cls._score(q, cls.LAW_HIGH, 3) +
            cls._score(q, cls.LAW_MID, 2) +
            cls._score(q, cls.LAW_LOW, 1)
        )
        case_score = (
            cls._score(q, cls.CASE_HIGH, 3) +
            cls._score(q, cls.CASE_MID, 2) +
            cls._score(q, cls.CASE_LOW, 1)
        )
        rule_score = (
            cls._score(q, cls.RULE_HIGH, 3) +
            cls._score(q, cls.RULE_MID, 2) +
            cls._score(q, cls.RULE_LOW, 1)
        )

        max_score = max(law_score, case_score, rule_score)
        if max_score < cls.GENERAL_THRESHOLD:
            return "general"

        scores = {"law": law_score, "case": case_score, "rule": rule_score}
        return max(scores, key=scores.get)

    @classmethod
    def _score(cls, query: str, patterns: list, weight: int) -> int:
        """计算查询文本在一组正则模式中的命中加权得分。"""
        score = 0
        for pat in patterns:
            if re.search(pat, query):
                score += weight
        return score

    @classmethod
    def debug_classify(cls, query: str) -> dict:
        """调试用：返回各类型详细得分。"""
        q = query.strip()
        law_h = cls._score(q, cls.LAW_HIGH, 3)
        law_m = cls._score(q, cls.LAW_MID, 2)
        law_l = cls._score(q, cls.LAW_LOW, 1)
        case_h = cls._score(q, cls.CASE_HIGH, 3)
        case_m = cls._score(q, cls.CASE_MID, 2)
        case_l = cls._score(q, cls.CASE_LOW, 1)
        rule_h = cls._score(q, cls.RULE_HIGH, 3)
        rule_m = cls._score(q, cls.RULE_MID, 2)
        rule_l = cls._score(q, cls.RULE_LOW, 1)
        return {
            "law": {"high": law_h, "mid": law_m, "low": law_l, "total": law_h + law_m + law_l},
            "case": {"high": case_h, "mid": case_m, "low": case_l, "total": case_h + case_m + case_l},
            "rule": {"high": rule_h, "mid": rule_m, "low": rule_l, "total": rule_h + rule_m + rule_l},
            "result": cls.classify(query),
        }


# ============================================================
# 自适应权重配置
# ============================================================

ADAPTIVE_WEIGHTS = {
    "law": {
        "w_vec": 0.60,
        "w_fts": 0.25,
        "w_time": 0.05,
        "w_conf": 0.10,
    },
    "case": {
        "w_vec": 0.45,
        "w_fts": 0.30,
        "w_time": 0.15,
        "w_conf": 0.10,
    },
    "rule": {
        "w_vec": 0.40,
        "w_fts": 0.35,
        "w_time": 0.10,
        "w_conf": 0.15,
    },
    "general": {
        "w_vec": 0.50,
        "w_fts": 0.20,
        "w_time": 0.10,
        "w_conf": 0.20,
    },
}

# 各查询类型对应的子库偏好权重（用于跨库结果的二次排序加成）
# 目标库正向加成 + 非目标库负向惩罚，确保跨库排序时目标库结果优先
LIB_BOOST = {
    "law": {"law": 1.50, "case": 0.70, "rule": 0.70},
    "case": {"law": 0.70, "case": 1.50, "rule": 0.70},
    "rule": {"law": 0.70, "case": 0.70, "rule": 1.50},
    "general": {"law": 1.00, "case": 1.00, "rule": 1.00},
}


# ============================================================
# ThreeLibRetriever
# ============================================================

class ThreeLibRetriever:
    """三库并行检索器，支持查询类型识别与自适应融合权重。"""

    SOURCES = {
        "law": ["ad_law"],
        "case": ["penalty_case"],
        "rule": ["industry_rule"],
    }

    def __init__(self, store: VmemStore, use_adaptive: bool = True):
        """
        Args:
            store: VmemStore 实例
            use_adaptive: 是否启用自适应权重（默认启用）
        """
        self.store = store
        self.use_adaptive = use_adaptive
        self.classifier = QueryClassifier()

    def retrieve(self, query: str, industry: str = "general", top_k: int = 5):
        """三库并行检索，返回合并后的 top 结果。

        根据查询类型自动选择融合权重，并对匹配类型的子库结果进行加权提升。

        Args:
            query: 查询文本
            industry: 行业标签，用于结果重排
            top_k: 返回结果数

        Returns:
            检索结果列表，每个结果包含 key/value/source/score/lib 等字段
        """
        # 1. 查询类型分类
        query_type = self.classifier.classify(query) if self.use_adaptive else "general"

        # 2. 获取对应权重
        weights = ADAPTIVE_WEIGHTS.get(query_type, ADAPTIVE_WEIGHTS["general"])

        # 3. 分别检索三个子库
        all_results = []
        for lib_name, sources in self.SOURCES.items():
            results = self.store.search(
                query, top_k=5, source_filter=sources,
                w_vec=weights["w_vec"],
                w_fts=weights["w_fts"],
                w_time=weights["w_time"],
                w_conf=weights["w_conf"],
            )
            for r in results:
                r["lib"] = lib_name
                # 自适应权重：对偏好子库的结果进行得分加成
                if self.use_adaptive and query_type != "general":
                    boost = LIB_BOOST.get(query_type, {}).get(lib_name, 1.0)
                    r["raw_score"] = r.get("score", 0)
                    r["score"] = r.get("score", 0) * boost
                else:
                    r["raw_score"] = r.get("score", 0)
            all_results.extend(results)

        # 4. 同行业结果优先
        if industry != "general":
            industry_tag = industry
            boosted = [r for r in all_results if industry_tag in r.get("tags", "")]
            other = [r for r in all_results if industry_tag not in r.get("tags", "")]
            all_results = boosted + other

        # 5. 去重
        seen = set()
        unique = []
        for r in all_results:
            key = r.get("key", "")
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # 6. 按 score 降序排列，确保跨库合并后高分结果优先
        unique.sort(key=lambda r: r.get("score", 0), reverse=True)

        return unique[:top_k]

    def get_query_type(self, query: str) -> str:
        """获取查询类型（便于调试和评测）。"""
        return self.classifier.classify(query)


# ---------------------------------------------------------------------------
# 验证脚本：直接运行本文件时执行
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[test] ThreeLibRetriever import 成功")
    print(f"[test] SOURCES = {ThreeLibRetriever.SOURCES}")

    # 测试 QueryClassifier
    print("\n[test] QueryClassifier 测试:")
    test_queries = [
        "全网最低价算不算违规",
        "绝对化用语的法律定义是什么",
        "某化妆品公司因虚假宣传被罚了多少",
        "抖音平台对广告内容有哪些审核规则",
        "广告法第九条规定了什么",
        "电商平台使用极限用语被处罚的案例",
        "小红书种草笔记需要标注广告吗",
        "保健食品广告有哪些要求",
    ]
    for q in test_queries:
        q_type = QueryClassifier.classify(q)
        print(f"  [{q_type}] {q}")

    print("\n[test] 自适应权重配置:")
    for q_type, w in ADAPTIVE_WEIGHTS.items():
        print(f"  {q_type}: vec={w['w_vec']:.2f} fts={w['w_fts']:.2f} "
              f"time={w['w_time']:.2f} conf={w['w_conf']:.2f}")

    print("\n[test] 子库偏好加成:")
    for q_type, boosts in LIB_BOOST.items():
        print(f"  {q_type}: {boosts}")

    print("[test] 类定义正常，等待数据入库后可进行检索测试")
