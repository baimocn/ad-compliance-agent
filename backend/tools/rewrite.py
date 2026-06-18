"""工具4：替代文案生成 — 基于禁用→替代映射表 + LLM 生成合规文案"""
import json
import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
from schemas import Suggestion
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


class RewriteGenerator:
    def __init__(self, llm: ChatOpenAI, replacement_source=None):
        self._llm = llm
        self._replacements = {}
        if isinstance(replacement_source, dict):
            self._replacements = replacement_source
        elif isinstance(replacement_source, str):
            self._load_replacements(replacement_source)

    def _load_replacements(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            for item in raw:
                self._replacements[item.get('prohibited', '')] = item.get('alternatives', [])
        except:
            pass

    def lookup(self, word: str) -> list[str]:
        """从映射表直接查找替代词"""
        return self._replacements.get(word, [])

    async def generate(self, original_text: str, violations: list[dict]) -> list[Suggestion]:
        """生成替代建议：先查映射表，查不到再用 LLM"""
        suggestions = []
        for v in violations:
            word = v.get('word', '')
            alternatives = self.lookup(word)
            if alternatives:
                suggestions.append(Suggestion(
                    original=word,
                    replacement=alternatives[0],
                    reason=f"从合规映射表匹配"
                ))
            else:
                # LLM 生成
                prompt = f"请为广告文案中的违规词「{word}」生成一个合规替代词。只输出替代词，不要解释。"
                try:
                    resp = await self._llm.ainvoke([HumanMessage(content=prompt)])
                    suggestions.append(Suggestion(
                        original=word,
                        replacement=resp.content.strip(),
                        reason="LLM 生成"
                    ))
                except:
                    suggestions.append(Suggestion(
                        original=word,
                        replacement="[需人工替换]",
                        reason="LLM 调用失败"
                    ))
        return suggestions
