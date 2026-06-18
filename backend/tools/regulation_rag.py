"""工具3：法规 RAG 检索 — 三库并行检索，返回法条+案例+替代建议"""
import sys
sys.path.insert(0, 'D:/Desktop/黑客松/pipeline')
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
from retrieval import ThreeLibRetriever
from storage import VmemStore


class RegulationRAG:
    def __init__(self, store: VmemStore):
        self._retriever = ThreeLibRetriever(store)

    def search(self, violation_desc: str, industry: str = "general", top_k: int = 5) -> list[dict]:
        return self._retriever.retrieve(violation_desc, industry=industry, top_k=top_k)

    def format_results(self, results: list[dict]) -> str:
        formatted = []
        for r in results:
            source = r.get('source', '')
            if source == 'ad_law':
                formatted.append(f"📖 法条：{r.get('value', '')[:200]}")
            elif source == 'penalty_case':
                formatted.append(f"📋 案例：{r.get('value', '')[:200]}")
            elif source == 'industry_rule':
                formatted.append(f"📌 规则：{r.get('value', '')[:200]}")
        return "\n---\n".join(formatted) if formatted else "未检索到相关法规"
