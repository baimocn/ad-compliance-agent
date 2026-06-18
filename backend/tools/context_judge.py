"""工具2：LLM 语境判断 — 对禁用词命中做语境判断，减少误报"""
import sys
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
from schemas import BannedWordHit, ContextJudgment
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


class ContextJudge:
    def __init__(self, llm: ChatOpenAI):
        self._llm = llm.with_structured_output(ContextJudgment)

    async def judge(self, text: str, hit: BannedWordHit, industry: str = "general") -> ContextJudgment:
        system = "你是广告法合规专家。判断禁用词在文案语境中是否构成违规。"\
                "\n规则：营销目的→违规；客观参数→不违规；不确定→标记违规（宁可误报不可漏报）。"

        user_msg = f"文案：{text}\n命中词：\"{hit.word}\"\n类别：{hit.category}\n行业：{industry}"

        return await self._llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user_msg),
        ])

    async def batch_judge(self, text: str, hits: list[BannedWordHit], industry: str = "general") -> list[ContextJudgment]:
        import asyncio
        tasks = [self.judge(text, hit, industry) for hit in hits]
        return await asyncio.gather(*tasks, return_exceptions=False)
