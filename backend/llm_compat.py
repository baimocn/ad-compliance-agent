"""兼容推理模型（mimo 等）的 LLM 包装器
这些模型把回复放在 reasoning_content 而不是 content，
langchain_openai 的 ChatOpenAI 无法正确处理。
"""
import json
from openai import AsyncOpenAI


class CompatibleLLM:
    """兼容层：提供与 langchain ChatOpenAI 相同的 ainvoke 接口"""

    def __init__(self, model: str, base_url: str, api_key: str, temperature: float = 0):
        self.model = model
        self.temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0)

    async def ainvoke(self, messages) -> "LLMResponse":
        """模拟 langchain ainvoke 接口"""
        # 转换 langchain 消息格式为 OpenAI 格式
        oai_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                role = getattr(msg, 'type', 'human')
                if role == 'system':
                    oai_messages.append({"role": "system", "content": msg.content})
                elif role in ('human', 'user'):
                    oai_messages.append({"role": "user", "content": msg.content})
                elif role in ('ai', 'assistant'):
                    oai_messages.append({"role": "assistant", "content": msg.content})
                else:
                    oai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, dict):
                oai_messages.append(msg)

        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            temperature=self.temperature,
            max_tokens=8192,
        )

        choice = resp.choices[0].message if resp.choices else None
        content = (choice.content or "") if choice else ""
        reasoning = getattr(choice, "reasoning_content", "") or ""

        # 推理模型：如果 content 为空但 reasoning 有内容，用 reasoning
        # 对于 JSON 解析场景，reasoning 里可能包含最终答案
        final_content = content.strip() if content.strip() else reasoning.strip()

        usage = resp.usage
        return LLMResponse(
            content=final_content,
            reasoning_content=reasoning,
            usage_metadata={
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
            }
        )


class LLMResponse:
    """模拟 langchain AIMessage"""
    def __init__(self, content: str, reasoning_content: str = "", usage_metadata: dict = None):
        self.content = content
        self.reasoning_content = reasoning_content
        self.usage_metadata = usage_metadata or {}
