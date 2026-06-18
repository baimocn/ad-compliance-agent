"""工具2：LLM 语境判断 — 对禁用词命中做语境判断，减少误报"""
import sys
import json
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
from schemas import BannedWordHit, ContextJudgment
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


class ContextJudge:
    def __init__(self, llm: ChatOpenAI):
        self._llm = llm

    async def judge(self, text: str, hit: BannedWordHit, industry: str = "general") -> ContextJudgment:
        system = "你是广告法合规专家。判断禁用词在文案语境中是否构成违规。"\
                "\n规则：营销目的→违规；客观参数→不违规；不确定→标记违规（宁可误报不可漏报）。"\
                "\n请严格按以下 JSON 格式输出，不要输出其他内容：\n"\
                '{"is_violation": true/false, "reasoning": "原因说明", "confidence": 0.0~1.0}'

        user_msg = f"文案：{text}\n命中词：\"{hit.word}\"\n类别：{hit.category}\n行业：{industry}"

        resp = await self._llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user_msg),
        ])

        content = resp.content.strip()
        # 提取 JSON 子串（兼容 LLM 输出含前缀/后缀文本）
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            data = json.loads(content[start:end + 1])
        else:
            data = json.loads(content)

        return ContextJudgment(
            is_violation=bool(data.get("is_violation", True)),
            reasoning=str(data.get("reasoning", "")),
            confidence=float(data.get("confidence", 0.5)),
        )

    async def batch_judge(self, text: str, hits: list[BannedWordHit], industry: str = "general") -> list[ContextJudgment]:
        import asyncio
        tasks = [self.judge(text, hit, industry) for hit in hits]
        return await asyncio.gather(*tasks, return_exceptions=False)
