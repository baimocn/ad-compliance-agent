"""广告法合规审查 Agent — 主编排"""
import sys
import time
import hashlib
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))
sys.path.insert(0, str(_PROJECT))

from schemas import (
    ReviewRequest, ReviewResponse, Violation, RiskLevel,
    Suggestion, RelatedCase, BannedWordHit
)
from tools.banned_word import BannedWordMatcher
from tools.context_judge import ContextJudge
from tools.regulation_rag import RegulationRAG
from tools.rewrite import RewriteGenerator
from storage import VmemStore
from langchain_openai import ChatOpenAI


class ComplianceAgent:
    def __init__(self, config):
        self._default_config = {
            "model": config.LLM_MODEL,
            "base_url": config.LLM_BASE_URL,
            "api_key": config.LLM_API_KEY,
            "temperature": 0,
        }
        # 默认 LLM
        self._llm = ChatOpenAI(**self._default_config)
        # 工具
        self._matcher = BannedWordMatcher(config.BANNED_WORDS_PATH)
        self._judge = ContextJudge(self._llm)
        self._store = VmemStore(config.DB_PATH)
        self._rag = RegulationRAG(self._store)
        self._rewriter = RewriteGenerator(self._llm, config.REPLACEMENT_PATH)

    def _get_llm(self, api_key: str = None, base_url: str = None) -> ChatOpenAI:
        """获取 LLM 客户端：前端传了就用前端的，否则用默认的"""
        if api_key and api_key.strip():
            return ChatOpenAI(
                model=self._default_config["model"],
                base_url=base_url or self._default_config["base_url"],
                api_key=api_key.strip(),
                temperature=0,
            )
        return self._llm

    async def review(self, request: ReviewRequest) -> ReviewResponse:
        start_time = time.time()
        review_id = f"CR-{int(start_time)}-{hashlib.md5(request.text.encode()).hexdigest()[:4]}"

        # 获取 LLM 客户端（前端传了 key 就用前端的）
        llm = self._get_llm(request.api_key, request.base_url)
        judge = ContextJudge(llm) if request.api_key else self._judge
        rewriter = RewriteGenerator(llm, self._rewriter._replacements) if request.api_key else self._rewriter

        # 累计 token 用量
        total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Step 1: 禁用词匹配（确定性，不走 LLM）
        hits = self._matcher.match(request.text)

        if not hits:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return ReviewResponse(
                review_id=review_id,
                status="safe",
                overall_risk=RiskLevel.PASS,
                violations=[],
                highlighted_text=request.text,
                summary="未发现违规内容。",
                reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                processing_time_ms=processing_time_ms,
                token_usage=total_token_usage,
            )

        # Step 2: LLM 语境判断（并发）
        judgments = await judge.batch_judge(request.text, hits, request.industry.value)

        # 过滤掉不违规的命中
        confirmed_hits = []
        for hit, judgment in zip(hits, judgments):
            if judgment.is_violation:
                confirmed_hits.append((hit, judgment))

        if not confirmed_hits:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return ReviewResponse(
                review_id=review_id,
                status="safe",
                overall_risk=RiskLevel.PASS,
                violations=[],
                highlighted_text=request.text,
                summary=f"检测到 {len(hits)} 个疑似禁用词，经语境分析均不构成违规。",
                reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                processing_time_ms=processing_time_ms,
                token_usage=total_token_usage,
            )

        # Step 3: RAG 检索法规依据
        violations = []
        for hit, judgment in confirmed_hits:
            rag_results = self._rag.search(hit.word, request.industry.value, top_k=3)

            # 确定风险等级
            severity = RiskLevel.HIGH if judgment.confidence > 0.8 else RiskLevel.MEDIUM

            violations.append(Violation(
                id=f"v-{hashlib.md5(hit.word.encode()).hexdigest()[:8]}",
                text=hit.word,
                start_index=hit.position[0],
                end_index=hit.position[1],
                severity=severity,
                category=hit.category,
                law_article=hit.regulation_ref,
                law_content=rag_results[0].get('value', '')[:200] if rag_results else "",
                explanation=judgment.reasoning,
                suggestions=[],
                related_cases=[],
            ))

        # Step 4: 生成替代建议
        suggestions = await rewriter.generate(
            request.text,
            [{'word': v.text, 'category': v.category} for v in violations]
        )
        for v, s in zip(violations, suggestions):
            v.suggestions = [s]

        # 生成高亮文本
        highlighted = self._highlight(request.text, violations)

        # 整体风险等级
        max_risk = max((v.severity for v in violations), key=lambda x: ["pass","low","medium","high"].index(x.value))

        processing_time_ms = int((time.time() - start_time) * 1000)
        return ReviewResponse(
            review_id=review_id,
            status="violation_found",
            overall_risk=max_risk,
            violations=violations,
            highlighted_text=highlighted,
            summary=f"检测到 {len(violations)} 处违规，最高风险等级：{max_risk.value}",
            reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            processing_time_ms=processing_time_ms,
            token_usage=total_token_usage,
        )

    def _highlight(self, text: str, violations: list[Violation]) -> str:
        """在文本中用 <mark> 标记违规位置"""
        result = text
        # 从后往前替换，避免位置偏移
        sorted_v = sorted(violations, key=lambda v: v.start_index, reverse=True)
        for v in sorted_v:
            color = {"high": "#ff4444", "medium": "#ffaa00", "low": "#ffdd00"}.get(v.severity.value, "#ffdd00")
            marked = f'<mark style="background:{color}" title="{v.category}: {v.explanation}">{v.text}</mark>'
            result = result[:v.start_index] + marked + result[v.end_index:]
        return result

    def close(self):
        self._store.close()
