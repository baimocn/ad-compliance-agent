"""工具2：LLM 语境判断 v2 — 分层判断架构，针对不同违规类型使用专用 prompt"""
import sys
import json
import re
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
from schemas import BannedWordHit, ContextJudgment
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


# ============================================================
# 违规类型映射：category → 违规大类
# ============================================================

VIOLATION_TYPE_MAP = {
    # 极限用语类
    "极限用语": "EXTREME_WORDS",
    "绝对化用语": "EXTREME_WORDS",
    # 虚假宣传类
    "虚假宣传": "FALSE_PROMOTION",
    "效果承诺": "FALSE_PROMOTION",
    "虚假数据": "FALSE_PROMOTION",
    "诱导焦虑": "FALSE_PROMOTION",  # 诱导焦虑属于虚假宣传范畴（制造焦虑以促进销售）
    "资质虚构": "FALSE_PROMOTION",  # 资质虚构属于虚假宣传范畴（虚假资质宣称）
    # 对比贬低类
    "对比贬低": "COMPETITION_DENIGRATE",
    "贬低同行": "COMPETITION_DENIGRATE",
    # 行业禁区类（作为额外类型）
    "行业禁区": "INDUSTRY_PROHIBITION",
    "医疗违规": "INDUSTRY_PROHIBITION",
    "金融违规": "INDUSTRY_PROHIBITION",
    "教育违规": "INDUSTRY_PROHIBITION",
    "房地产违规": "INDUSTRY_PROHIBITION",
    "食品违规": "INDUSTRY_PROHIBITION",
    "化妆品违规": "INDUSTRY_PROHIBITION",
}


def _get_violation_type(category: str) -> str:
    """根据禁用词类别判断违规大类。"""
    # 精确匹配
    if category in VIOLATION_TYPE_MAP:
        return VIOLATION_TYPE_MAP[category]
    # 模糊匹配
    for key, vtype in VIOLATION_TYPE_MAP.items():
        if key in category or category in key:
            return vtype
    return "EXTREME_WORDS"  # 默认归类


# ============================================================
# 专用 Prompt 定义（按违规类型分层）
# ============================================================

# ---- 共用基础规则 ----
COMMON_BASE_RULES = """
## 核心原则
宁可误报不可漏报。只要有营销宣传意图，就应标记为违规。

## 通用判断规则
1. 有明确营销/推广/销售目的 → 倾向违规
2. 纯客观事实陈述（参数、规格、成分、型号等）→ 不违规
3. 主观个人评价且无营销意图（个人觉得、我觉得等）→ 不违规
4. 引用第三方权威数据且可溯源 → 视情况判定
5. 加了限定词的表述仍有营销意图 → 仍标记违规（降低风险等级）
"""

# ---- 极限用语专用判断规则 ----
EXTREME_WORDS_RULES = """
## 【极限用语】专项判断规则

### 违规判定要点（重点检查）
1. **营销意图强度**：是否用于产品/服务推广宣传？
   - 是 → 违规
   - 否（纯客观参数、技术规格）→ 不违规

2. **绝对化程度**：
   - 顶级绝对化（最佳、第一、最高、最低、国家级、最有效）→ 高风险违规
   - 较强绝对化（领先、顶级、极致、完美、终极）→ 中高风险违规
   - 弱化绝对化（比较好、相对领先、之一）→ 中低风险违规

3. **限定词软化效果**：
   - 可能是最好的之一、约提升、相对 → 降低风险但仍违规
   - 纯客观描述（最大支持128G、最高频率3.5GHz）→ 不违规

4. **语境区分**：
   - 商品标题、详情页、广告语 → 倾向违规
   - 技术文档、规格说明、参数表 → 倾向不违规
   - 用户评价、个人分享 → 不违规（非广告主发布）
"""

# ---- 虚假宣传专用判断规则 ----
FALSE_PROMOTION_RULES = """
## 【虚假宣传】专项判断规则

### 违规判定要点（重点检查）
1. **量化承诺程度**：
   - 具体数值承诺（99%治愈率、三天瘦10斤、100%有效）→ 高风险违规
   - 模糊效果暗示（显著改善、效果明显、快速见效）→ 中风险违规
   - 主观感受描述（感觉不错、用着挺好）→ 低风险或不违规

2. **效果可证实性**：
   - 有科学依据、临床数据、第三方认证 → 降低风险
   - 无依据的断言、保证、承诺 → 高风险违规
   - "无效退款""包治百病""永不复发" → 高风险违规

3. **暗示与明示的区分**：
   - 明示效果（包瘦、根治、治愈）→ 违规
   - 暗示效果（"用了都说好""大家都在买"）→ 违规（口碑型虚假宣传）
   - 纯成分陈述（含维生素C、添加烟酰胺）→ 不违规

4. **行业敏感性**：
   - 医疗/药品/保健食品 → 更严格（效果暗示也违规）
   - 普通消费品 → 相对宽松（明显虚假才违规）
   - 教育/金融 → 严格（不得作保证性承诺）
"""

# ---- 对比贬低专用判断规则 ----
COMPETITION_DENIGRATE_RULES = """
## 【对比贬低】专项判断规则

### 违规判定要点（重点检查）
1. **是否直接贬低竞争对手**：
   - 点名贬低某品牌/产品（"比XX品牌好""XX牌就是不行"）→ 高风险违规
   - 泛指贬低同行（"行业内最差""同行都做不到"）→ 中风险违规
   - 客观参数对比且数据真实 → 不违规

2. **贬义词强度**：
   - 强烈贬义词（劣质、垃圾、骗人、虚假、黑心）→ 高风险违规
   - 中等贬义词（不如、比不上、差远了）→ 中风险违规
   - 中性对比（更高、更快、更轻）→ 需看是否有数据支撑

3. **对比数据真实性**：
   - 有第三方检测报告、权威数据 → 降低风险
   - 无依据的主观对比断言 → 违规
   - 故意歪曲竞争对手参数 → 高风险违规

4. **对比的公平性**：
   - 拿自己优势比对方劣势（不公平对比）→ 违规
   - 同等条件下的客观参数对比 → 不违规
   - "行业领先""远超同行"等无数据支撑 → 违规
"""

# ---- 行业禁区专用判断规则（附加） ----
INDUSTRY_PROHIBITION_RULES = """
## 【行业禁区】专项判断规则

### 违规判定要点（重点检查）
1. **是否涉及行业禁止内容**：
   - 医疗：治愈率、有效率、患者代言、保证治愈 → 违规
   - 药品：处方药广告、无效退款、无毒副作用 → 违规
   - 保健食品：疾病治疗功能、代言人推荐 → 违规
   - 金融：保本保息、零风险、稳赚不赔 → 违规
   - 教育：保过、包过、命题组老师 → 违规
   - 房地产：升值承诺、投资回报、时间距离表述 → 违规

2. **行业匹配度**：
   - 文案行业与违规内容匹配 → 加重违规
   - 文案行业不相关 → 降低风险或不违规

3. **表述的明确性**：
   - 直接表述禁止内容 → 高风险违规
   - 间接暗示 → 中风险违规
   - 仅提及行业名词但无违规内容 → 不违规
"""


# ============================================================
# Prompt 组装器
# ============================================================

def _build_system_prompt(violation_type: str) -> str:
    """根据违规类型组装对应的系统 prompt。"""
    type_specific_rules = {
        "EXTREME_WORDS": EXTREME_WORDS_RULES,
        "FALSE_PROMOTION": FALSE_PROMOTION_RULES,
        "COMPETITION_DENIGRATE": COMPETITION_DENIGRATE_RULES,
        "INDUSTRY_PROHIBITION": INDUSTRY_PROHIBITION_RULES,
    }

    specific_rules = type_specific_rules.get(violation_type, "")

    output_format = """
## 输出格式（严格 JSON）
{
  "is_violation": true/false,
  "violation_type": "EXTREME_WORDS/FALSE_PROMOTION/COMPETITION_DENIGRATE/INDUSTRY_PROHIBITION/NONE",
  "reasoning": "一句话总结判断理由",
  "evidence": ["证据点1", "证据点2", "证据点3"],
  "mitigating_factors": ["减轻因素1", "减轻因素2"],
  "overall_confidence": 0.0~1.0,
  "violation_type_confidence": 0.0~1.0,
  "severity_confidence": 0.0~1.0,
  "context_relevance": 0.0~1.0,
  "suggested_severity": "high/medium/low/pass"
}

## 置信度说明
- overall_confidence: 整体违规判定置信度
- violation_type_confidence: 对违规类型归类的置信度
- severity_confidence: 对风险等级判定的置信度
- context_relevance: 语境与营销意图的相关程度（越高越像广告）

## 风险等级说明
- high: 明显违规，有明确营销意图和强违规表述
- medium: 疑似违规，有营销意图但表述有模糊空间
- low: 轻微违规或边界情况，有减轻因素
- pass: 不违规，纯客观陈述或无营销意图
"""

    return (
        f"你是广告法合规专家，专长判断【{violation_type}】类违规。"
        f"请根据文案语境判断禁用词命中是否构成《广告法》违规。\n\n"
        f"{COMMON_BASE_RULES}\n"
        f"{specific_rules}\n"
        f"{output_format}"
    )


# ============================================================
# ContextJudge v2 — 分层判断架构
# ============================================================

class ContextJudge:
    """语境判断器 v2 — 分层判断架构，针对不同违规类型使用专用 prompt。

    核心改进：
    1. 按违规类型分层使用专用判断 prompt（而非统一 prompt）
    2. 多维度置信度输出（overall / violation_type / severity / context_relevance）
    3. 结构化推理输出（reasoning / evidence / mitigating_factors / suggested_severity）
    4. LLM 并发控制（asyncio.Semaphore，默认 3 并发）
    5. 反馈闭环学习：根据历史反馈动态调整置信度
    """

    def __init__(self, llm: ChatOpenAI, max_concurrency: int = 3, timeout_s: int = 15):
        self._llm = llm
        import asyncio
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._timeout_s = timeout_s
        self._max_concurrency = max_concurrency
        # 反馈历史记录：{word: {confirm: n, dismiss: n, total: n}}
        self._feedback_history: dict[str, dict] = {}

    async def judge(
        self,
        text: str,
        hit: BannedWordHit,
        industry: str = "general",
    ) -> ContextJudgment:
        """判断禁用词在文案语境中是否构成违规。

        Args:
            text: 完整文案文本
            hit: 禁用词命中信息
            industry: 行业标签

        Returns:
            ContextJudgment — 包含多维度置信度和结构化推理
        """
        import asyncio

        # 1. 判断违规大类，选择对应 prompt
        violation_type = _get_violation_type(hit.category)
        system_prompt = _build_system_prompt(violation_type)

        user_msg = (
            f"文案：{text}\n"
            f"命中词：\"{hit.word}\"\n"
            f"命中类别：{hit.category}\n"
            f"违规类型：{violation_type}\n"
            f"行业：{industry}\n"
            f"法规参考：{hit.regulation_ref}"
        )

        # 2. LLM 调用（带信号量、超时、重试）
        max_retries = 3
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                # 获取信号量许可（控制 LLM 并发数）
                async with self._semaphore:
                    # 超时控制
                    resp = await asyncio.wait_for(
                        self._llm.ainvoke([
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=user_msg),
                        ]),
                        timeout=self._timeout_s,
                    )

                content = resp.content.strip()
                data = self._parse_json(content)
                judgment = self._build_judgment(data, hit, violation_type)

                # 3. 应用反馈学习：根据历史反馈调整置信度
                judgment = self._apply_feedback_learning(hit.word, judgment)

                return judgment

            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        # 所有重试均失败，安全降级
        return ContextJudgment(
            is_violation=True,
            reasoning=f"LLM 调用失败，安全降级标记为疑似违规：{str(last_error)}",
            confidence=0.5,
            violation_type_confidence=0.3,
            severity_confidence=0.3,
            context_relevance=0.5,
            evidence=["LLM 调用失败，安全降级"],
            mitigating_factors=["系统异常，需人工复核"],
            suggested_severity="medium",
            violation_type=violation_type,
        )

    async def batch_judge(
        self,
        text: str,
        hits: list[BannedWordHit],
        industry: str = "general",
    ) -> list[ContextJudgment]:
        """批量判断多个禁用词命中。"""
        import asyncio
        tasks = [self.judge(text, hit, industry) for hit in hits]
        return await asyncio.gather(*tasks, return_exceptions=False)

    # ---- 反馈学习相关 ----

    def record_feedback(self, word: str, action: str):
        """记录用户反馈，用于后续置信度动态调整。

        Args:
            word: 禁用词
            action: "confirm"（确认违规）| "dismiss"（驳回，不违规）| "modify"（修改）
        """
        if word not in self._feedback_history:
            self._feedback_history[word] = {"confirm": 0, "dismiss": 0, "modify": 0, "total": 0}
        hist = self._feedback_history[word]
        if action in hist:
            hist[action] += 1
        hist["total"] += 1

    def get_feedback_stats(self, word: str) -> dict:
        """获取某个禁用词的反馈统计。"""
        return self._feedback_history.get(word, {"confirm": 0, "dismiss": 0, "modify": 0, "total": 0})

    def _apply_feedback_learning(self, word: str, judgment: ContextJudgment) -> ContextJudgment:
        """根据历史反馈调整置信度。

        规则：
        - 同一禁用词过去 10 次反馈中，8 次以上为 dismiss → 降低置信度
        - 同一禁用词过去 10 次反馈中，8 次以上为 confirm → 提升置信度
        """
        hist = self._feedback_history.get(word)
        if not hist or hist["total"] < 5:  # 反馈样本不足，不调整
            return judgment

        total = hist["total"]
        dismiss_rate = hist["dismiss"] / total
        confirm_rate = hist["confirm"] / total

        adjusted = judgment.model_copy()

        # 80% 以上被驳回 → 降低置信度（更倾向判为不违规）
        if dismiss_rate >= 0.8 and total >= 8:
            adjustment = min(0.3, dismiss_rate * 0.5)
            adjusted.confidence = max(0.1, adjusted.confidence - adjustment)
            adjusted.violation_type_confidence = max(0.1, adjusted.violation_type_confidence - adjustment)
            # 高驳回率下，如果原判定为违规且置信度低，则翻转或降低等级
            if adjusted.is_violation and adjusted.confidence < 0.4:
                adjusted.is_violation = False
                adjusted.suggested_severity = "pass"
                adjusted.mitigating_factors.append(
                    f"根据 {total} 次历史反馈中 {hist['dismiss']} 次被驳回，系统自动调整为不违规"
                )

        # 80% 以上被确认 → 提升置信度
        elif confirm_rate >= 0.8 and total >= 8:
            adjustment = min(0.2, confirm_rate * 0.3)
            adjusted.confidence = min(0.99, adjusted.confidence + adjustment)
            adjusted.violation_type_confidence = min(0.99, adjusted.violation_type_confidence + adjustment)

        return adjusted

    # ---- 内部方法 ----

    @staticmethod
    def _parse_json(content: str) -> dict:
        """从 LLM 输出中解析 JSON（兼容各种包装格式）。"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 提取 JSON 子串（兼容 ```json ... ``` 包裹）
        content = content.strip()
        if content.startswith("```"):
            # 去掉代码块标记
            end_marker = content.rfind("```")
            if end_marker > 3:
                content = content[3:end_marker].strip()
                # 去掉可能的 json 语言标记
                if content.lower().startswith("json"):
                    content = content[4:].strip()

        # 提取第一个 { 到最后一个 } 之间的内容
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end + 1])

        raise ValueError(f"无法解析 LLM 输出为 JSON: {content[:200]}")

    @staticmethod
    def _build_judgment(data: dict, hit: BannedWordHit, default_type: str) -> ContextJudgment:
        """从 LLM 返回的 JSON 构建 ContextJudgment 对象。"""
        is_violation = bool(data.get("is_violation", True))
        overall_conf = float(data.get("overall_confidence", data.get("confidence", 0.5)))

        # 多维度置信度
        vtype_conf = float(data.get("violation_type_confidence", overall_conf * 0.9))
        severity_conf = float(data.get("severity_confidence", overall_conf * 0.85))
        context_rel = float(data.get("context_relevance", overall_conf * 0.8))

        # 钳制到 [0, 1]
        def _clamp(v):
            return max(0.0, min(1.0, v))

        overall_conf = _clamp(overall_conf)
        vtype_conf = _clamp(vtype_conf)
        severity_conf = _clamp(severity_conf)
        context_rel = _clamp(context_rel)

        # 结构化推理
        reasoning = str(data.get("reasoning", ""))
        evidence = data.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        elif not isinstance(evidence, list):
            evidence = []
        evidence = [str(e) for e in evidence]

        mitigating = data.get("mitigating_factors", [])
        if isinstance(mitigating, str):
            mitigating = [mitigating]
        elif not isinstance(mitigating, list):
            mitigating = []
        mitigating = [str(m) for m in mitigating]

        suggested_severity = str(data.get("suggested_severity", "medium")).lower()
        if suggested_severity not in ("high", "medium", "low", "pass"):
            suggested_severity = "medium"

        violation_type = str(data.get("violation_type", default_type))

        return ContextJudgment(
            is_violation=is_violation,
            reasoning=reasoning,
            confidence=overall_conf,
            violation_type_confidence=vtype_conf,
            severity_confidence=severity_conf,
            context_relevance=context_rel,
            evidence=evidence,
            mitigating_factors=mitigating,
            suggested_severity=suggested_severity,
            violation_type=violation_type,
        )


# ============================================================
# 验证脚本
# ============================================================
if __name__ == "__main__":
    print("[test] ContextJudge v2 import 成功")
    print(f"[test] 违规类型映射: {VIOLATION_TYPE_MAP}")

    # 测试违规类型映射
    test_cats = ["极限用语", "虚假宣传", "对比贬低", "行业禁区", "医疗违规", "未知类型"]
    print("\n[test] 违规类型映射测试:")
    for cat in test_cats:
        vtype = _get_violation_type(cat)
        print(f"  [{cat}] → {vtype}")

    # 测试 prompt 构建
    print("\n[test] Prompt 构建测试:")
    for vtype in ["EXTREME_WORDS", "FALSE_PROMOTION", "COMPETITION_DENIGRATE", "INDUSTRY_PROHIBITION"]:
        prompt = _build_system_prompt(vtype)
        print(f"  {vtype}: prompt 长度 = {len(prompt)} 字符")

    print("\n[test] 类定义正常，需配置 LLM 后进行实际判断测试")
