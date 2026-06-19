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
        import asyncio

        system = (
            "你是广告法合规专家。判断禁用词在文案语境中是否构成《广告法》违规。\n\n"
            "## 核心原则\n"
            "宁可误报不可漏报。只要有营销宣传意图，就应标记为违规。\n\n"
            "## 判断规则\n"
            "1. 营销目的使用绝对化用语（最好、第一、最低、国家级、最强等）→ 违规\n"
            "2. 客观产品参数（材质、规格、成分、处理器型号等纯事实陈述）→ 不违规\n"
            "3. 主观个人评价且无营销意图（个人觉得、我觉得等）→ 不违规\n"
            "4. 口碑描述无数据支撑（都说好、回购率超高、口碑最好）→ 违规\n"
            "5. 极限促销话术（史上最强、错过等一年）→ 违规\n"
            "6. 效果暗示（轻松搞定、成绩提高）→ 违规\n"
            "7. 对比陈述（相比传统方案更优）→ 违规\n"
            "8. 权威暗示（航天级、行业内都知道）→ 违规\n"
            "9. 数据陈述含宣传意图（三个月突破百万）→ 违规\n"
            "10. 加了限定词的极限用语（可能最高之一、约提升）→ 仍标记违规（低风险）\n\n"
            "## 风险等级\n"
            "- confidence > 0.8 → 高风险\n"
            "- confidence 0.5-0.8 → 中风险\n"
            "- confidence < 0.5 → 低风险\n\n"
            "请严格按 JSON 格式输出：\n"
            '{"is_violation": true/false, "reasoning": "原因", "confidence": 0.0~1.0}'
        )

        user_msg = f"文案：{text}\n命中词：\"{hit.word}\"\n类别：{hit.category}\n行业：{industry}"

        max_retries = 3
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
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
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        # 所有重试均失败，安全降级
        return ContextJudgment(
            is_violation=True,
            confidence=0.5,
            reasoning="LLM 调用失败，安全降级标记为疑似违规",
        )

    async def batch_judge(self, text: str, hits: list[BannedWordHit], industry: str = "general") -> list[ContextJudgment]:
        import asyncio
        tasks = [self.judge(text, hit, industry) for hit in hits]
        return await asyncio.gather(*tasks, return_exceptions=False)
