"""
ThreeLibRetriever — 三库并行检索器
分别检索 law / case / rule 三个子库，合并、去重后返回 top 结果。
"""

from storage import VmemStore


class ThreeLibRetriever:
    """三库并行检索器"""

    SOURCES = {
        "law": ["ad_law"],
        "case": ["penalty_case"],
        "rule": ["industry_rule"],
    }

    def __init__(self, store: VmemStore):
        self.store = store

    def retrieve(self, query: str, industry: str = "general", top_k: int = 5):
        """三库并行检索，返回合并后的 top 结果"""
        all_results = []

        # 分别检索三个子库
        for lib_name, sources in self.SOURCES.items():
            results = self.store.search(query, top_k=3, source_filter=sources)
            for r in results:
                r["lib"] = lib_name
            all_results.extend(results)

        # 同行业结果优先
        if industry != "general":
            industry_tag = industry
            boosted = [r for r in all_results if industry_tag in r.get("tags", "")]
            other = [r for r in all_results if industry_tag not in r.get("tags", "")]
            all_results = boosted + other

        # 去重
        seen = set()
        unique = []
        for r in all_results:
            key = r.get("key", "")
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # 按 score 降序排列，确保跨库合并后高分结果优先
        unique.sort(key=lambda r: r.get("score", 0), reverse=True)

        return unique[:top_k]


# ---------------------------------------------------------------------------
# 验证脚本：直接运行本文件时执行（仅验证 import，不测检索）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[test] ThreeLibRetriever import 成功")
    print(f"[test] SOURCES = {ThreeLibRetriever.SOURCES}")
    print("[test] 类定义正常，等待数据入库后可进行检索测试")
