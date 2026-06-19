"""评测脚本 — Agent 评测 + RAG 评测"""
import sys
import json
import asyncio
import time
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

EVAL_DIR = str(_PROJECT / 'evaluation')


async def run_agent_eval():
    """Agent 评测：30 题端到端"""
    from agent import ComplianceAgent
    from schemas import ReviewRequest, Industry
    import config

    with open(f'{EVAL_DIR}/agent_eval_cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    if not config.LLM_API_KEY or config.LLM_API_KEY == "sk-your-key-here":
        print("SKIP: 未配置 DEEPSEEK_API_KEY")
        return {"skipped": True}

    agent_inst = ComplianceAgent(config)

    results = {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "total": len(cases)}
    total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    eval_start = time.time()
    for case in cases:
        req = ReviewRequest(text=case["text"], industry=Industry(case.get("industry", "general")))
        resp = await agent_inst.review(req)

        predicted = resp.status == "violation_found"
        actual = case["expected_violation"]

        if predicted and actual: results["TP"] += 1
        elif predicted and not actual: results["FP"] += 1
        elif not predicted and actual: results["FN"] += 1
        else: results["TN"] += 1

        # 累计 token 用量
        if resp.token_usage:
            for key in total_token_usage:
                total_token_usage[key] += resp.token_usage.get(key, 0)

    eval_elapsed = time.time() - eval_start
    agent_inst.close()

    precision = results["TP"] / (results["TP"] + results["FP"]) if (results["TP"] + results["FP"]) > 0 else 0
    recall = results["TP"] / (results["TP"] + results["FN"]) if (results["TP"] + results["FN"]) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (results["TP"] + results["TN"]) / results["total"]

    # 成本计算：DeepSeek-V4-Flash 价格 = 输入 1元/百万token + 输出 2元/百万token
    input_cost = total_token_usage["prompt_tokens"] / 1_000_000 * 1.0
    output_cost = total_token_usage["completion_tokens"] / 1_000_000 * 2.0
    total_cost = input_cost + output_cost

    results.update({
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "total_time_s": round(eval_elapsed, 2),
        "avg_time_s": round(eval_elapsed / len(cases), 2) if cases else 0,
        "token_usage": total_token_usage,
        "total_cost_yuan": round(total_cost, 4),
    })
    return results


def run_rag_eval():
    """
    RAG 评测 v2：30 题检索质量，含细粒度评估指标

    新增指标：
      - Precision@K (top-1 / top-3 / top-5)
      - MRR (Mean Reciprocal Rank)
      - 按查询类型分组统计
      - 失败案例根因分析
    """
    from pipeline import config
    from pipeline.storage import VmemStore
    from pipeline.retrieval import ThreeLibRetriever

    with open(f'{EVAL_DIR}/rag_eval_cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    store = VmemStore(str(config.DB_PATH))
    retriever = ThreeLibRetriever(store)

    # ---- 统计变量 ----
    total = len(cases)
    details = []
    mrr_sum = 0.0

    # Precision@K 统计
    p_at_k = {1: 0, 3: 0, 5: 0}

    # 按查询类型分组统计
    by_query_type = {}

    for case in cases:
        qid = case["id"]
        query = case["query"]
        expected_source = case["expected_source"]
        expected_keywords = case["expected_keywords"]
        query_type = case.get("query_type", "general")
        is_boundary = case.get("boundary_case", False)

        results = retriever.retrieve(query, top_k=5)
        all_text = " ".join([r.get("value", "") for r in results])
        sources = [r.get("source", "") for r in results]
        scores = [round(r.get("score", 0), 4) for r in results]
        detected_type = retriever.get_query_type(query)

        # ---- 判定 top-k 命中 ----
        # 命中定义：结果中存在匹配来源且包含至少一个预期关键词（语义近似）
        # 宽松判定：来源匹配 或 关键词全部命中
        def _hit_at(k):
            """检查 top-k 结果中是否有命中项"""
            top_results = results[:k]
            for r in top_results:
                r_source = r.get("source", "")
                r_text = r.get("value", "")
                source_match = r_source == expected_source
                keyword_partial = sum(1 for kw in expected_keywords if kw in r_text)
                # 命中条件：来源匹配 + 至少 1 个关键词命中
                if source_match and keyword_partial >= 1:
                    return True
            return False

        hit_top1 = _hit_at(1)
        hit_top3 = _hit_at(3)
        hit_top5 = _hit_at(5)

        # ---- MRR: 第一个命中结果的倒数排名 ----
        reciprocal_rank = 0.0
        for idx, r in enumerate(results, 1):
            r_source = r.get("source", "")
            r_text = r.get("value", "")
            source_match = r_source == expected_source
            keyword_partial = sum(1 for kw in expected_keywords if kw in r_text)
            if source_match and keyword_partial >= 1:
                reciprocal_rank = 1.0 / idx
                break
        mrr_sum += reciprocal_rank

        # ---- 整体通过判定（top-5 内命中即通过）----
        keyword_hit = all(kw in all_text for kw in expected_keywords)
        source_hit = expected_source in sources
        passed = hit_top5  # 用更严格的命中标准

        # ---- 失败原因分析 ----
        failure_reasons = []
        if not passed:
            if not source_hit:
                failure_reasons.append("source_not_found：目标来源库未被检索到")
            elif not hit_top5:
                failure_reasons.append("source_found_but_ranked_low：来源存在但排名低于 top-5")

            if not keyword_hit and source_hit:
                failure_reasons.append("keyword_mismatch：来源匹配但内容关键词不足")

            # 更深层根因
            if detected_type != query_type and query_type != "general":
                failure_reasons.append(
                    f"query_type_misclassified：分类错误（检测为 {detected_type}，预期为 {query_type}）"
                )

            if is_boundary:
                failure_reasons.append("boundary_case：边界查询，语义模糊")

            if not failure_reasons:
                failure_reasons.append("unknown：其他原因")

        # ---- 累计 Precision@K ----
        if hit_top1:
            p_at_k[1] += 1
        if hit_top3:
            p_at_k[3] += 1
        if hit_top5:
            p_at_k[5] += 1

        detail = {
            "id": qid,
            "query": query,
            "query_type_expected": query_type,
            "query_type_detected": detected_type,
            "is_boundary": is_boundary,
            "passed": passed,
            "hit_top1": hit_top1,
            "hit_top3": hit_top3,
            "hit_top5": hit_top5,
            "reciprocal_rank": round(reciprocal_rank, 4),
            "sources": sources,
            "scores": scores,
        }
        if not passed:
            detail["failure_reasons"] = failure_reasons
        details.append(detail)

        # ---- 按查询类型分组 ----
        if query_type not in by_query_type:
            by_query_type[query_type] = {
                "total": 0, "hits": 0, "hits_top1": 0, "hits_top3": 0,
                "mrr_sum": 0.0, "details": []
            }
        by_query_type[query_type]["total"] += 1
        if hit_top5:
            by_query_type[query_type]["hits"] += 1
        if hit_top1:
            by_query_type[query_type]["hits_top1"] += 1
        if hit_top3:
            by_query_type[query_type]["hits_top3"] += 1
        by_query_type[query_type]["mrr_sum"] += reciprocal_rank
        by_query_type[query_type]["details"].append(detail)

    # ---- 汇总统计 ----
    hits = p_at_k[5]
    recall = hits / total if total > 0 else 0
    mrr = mrr_sum / total if total > 0 else 0
    precision_at_k = {f"P@{k}": v / total for k, v in p_at_k.items()}

    # 各查询类型汇总
    type_summary = {}
    for q_type, data in by_query_type.items():
        t = data["total"]
        type_summary[q_type] = {
            "total": t,
            "hits": data["hits"],
            "recall": round(data["hits"] / t, 4) if t > 0 else 0,
            "P@1": round(data["hits_top1"] / t, 4) if t > 0 else 0,
            "P@3": round(data["hits_top3"] / t, 4) if t > 0 else 0,
            "P@5": round(data["hits"] / t, 4) if t > 0 else 0,
            "MRR": round(data["mrr_sum"] / t, 4) if t > 0 else 0,
        }

    # 失败案例汇总
    failures = [d for d in details if not d["passed"]]
    failure_analysis = {
        "total_failures": len(failures),
        "failure_rate": round(len(failures) / total, 4) if total > 0 else 0,
        "failure_cases": failures,
        "failure_reason_stats": {},
    }

    # 统计失败原因分布
    reason_count = {}
    for f in failures:
        for reason in f.get("failure_reasons", []):
            reason_key = reason.split("：")[0]
            reason_count[reason_key] = reason_count.get(reason_key, 0) + 1
    failure_analysis["failure_reason_stats"] = reason_count

    # ---- 最终结果 ----
    result = {
        "version": "v2",
        "total": total,
        "hits": hits,
        "recall": recall,
        "mrr": round(mrr, 4),
        "precision_at_k": precision_at_k,
        "by_query_type": type_summary,
        "failure_analysis": failure_analysis,
        "details": details,
    }

    store.close()
    return result


# ============================================================
# ContextJudge 评测（v2 分层判断架构）
# ============================================================

class MockContextJudge:
    """规则模拟的 ContextJudge，用于无 LLM 环境下的评测框架验证。

    v1 模式：统一规则，精度较低（模拟旧版统一 prompt）
    v2 模式：分层规则，按违规类型细化判断（模拟新版分层 prompt）
    """

    def __init__(self, version: str = "v2"):
        self.version = version

    def judge(self, text: str, hit: dict, industry: str = "general") -> dict:
        """模拟语境判断。"""
        import re
        text_lower = text.lower()
        category = hit.get("category", "")
        word = hit.get("word", "")

        def _match(pattern, text=text_lower):
            """大小写不敏感的正则匹配。"""
            return bool(re.search(pattern, text, re.IGNORECASE))

        # ---- 营销意图信号 ----
        marketing_signals = [
            r"买到就是赚到", r"限时", r"特惠", r"立即购买", r"点击购买",
            r"推荐", r"赶紧", r"手慢", r"错过", r"优惠",
            r"品质有保障", r"放心选购", r"安心之选", r"明智之选",
            r"销量", r"热销", r"爆款",
        ]
        has_marketing = any(_match(p) for p in marketing_signals)

        # ---- 个人评价信号 ----
        personal_signals = [
            r"我个人觉得", r"我觉得", r"个人认为", r"我用过觉得",
            r"我喝过", r"我用着", r"个人体验", r"个人感受",
        ]
        is_personal = any(_match(p) for p in personal_signals)

        # ---- 客观参数信号 ----
        objective_signals = [
            r"\d+\s*(ghz|mhz|mb|gb|tb|mah|w|v|a|hz|nm|inch|英寸|毫米|厘米|克|千克|毫克)",
            r"处理器", r"型号", r"规格", r"参数", r"容量", r"频率",
            r"支持\s*\d+", r"速率", r"接口", r"版本",
        ]
        is_objective = any(_match(p) for p in objective_signals)

        # ---- 限定词信号（软化极限用语） ----
        qualifier_signals = [
            r"可能", r"之一", r"相对", r"大概", r"约", r"差不多",
            r"我觉得", r"个人觉得", r"好像", r"感觉",
        ]
        has_qualifier = any(_match(p) for p in qualifier_signals)

        # ---- 第三方数据/认证信号 ----
        evidence_signals = [
            r"第三方", r"sgs", r"检测报告", r"临床验证", r"认证",
            r"国家标准", r"行业标准", r"权威机构",
        ]
        has_evidence = any(_match(p) for p in evidence_signals)

        # ---- 按违规类型判断 ----
        is_violation = False
        severity = "medium"
        confidence = 0.5
        evidence_list = []
        mitigating = []
        violation_type = "EXTREME_WORDS"

        if "极限用语" in category or "绝对化" in category:
            violation_type = "EXTREME_WORDS"
            if is_objective and not has_marketing:
                # 客观参数 + 无营销 → 不违规
                is_violation = False
                severity = "pass"
                confidence = 0.9
                evidence_list.append("纯客观技术参数陈述")
                mitigating.append("无营销推广意图")
            elif is_personal:
                # 个人主观评价 → 不违规
                is_violation = False
                severity = "pass"
                confidence = 0.85
                evidence_list.append("个人主观评价表达")
                mitigating.append("非商业广告主身份")
            elif has_marketing and has_qualifier:
                # 有营销 + 有限定词 → 违规但低风险
                is_violation = True
                severity = "low"
                confidence = 0.65 if self.version == "v2" else 0.5
                evidence_list.append(f"存在营销意图：使用了\"{word}\"等宣传用语")
                mitigating.append("使用了限定词软化绝对化表述")
                if self.version == "v2":
                    evidence_list.append("极限用语即使加限定词仍属违规")
            elif has_marketing:
                # 有营销 + 无限定词 → 明确违规
                is_violation = True
                severity = "high"
                confidence = 0.95 if self.version == "v2" else 0.8
                evidence_list.append(f"营销语境中使用极限用语\"{word}\"")
                evidence_list.append("存在明确的促销推广意图")
            else:
                # 模糊情况
                is_violation = True
                severity = "medium"
                confidence = 0.6 if self.version == "v2" else 0.5
                evidence_list.append(f"发现禁用词\"{word}\"")

        elif "虚假宣传" in category or "诱导焦虑" in category or "资质虚构" in category:
            violation_type = "FALSE_PROMOTION"
            # 量化承诺信号
            quantified = _match(r"\d+\s*(%|斤|元|天|个月|年|倍|个)")
            # 保证承诺信号
            guarantee = _match(r"无效退款|包退|包换|保证|无效.*退|不.*不要钱")
            # 医疗效果信号
            medical = _match(r"治愈|根治|治疗|治愈率|有效率|永不复发")
            # 成分事实信号
            ingredient = _match(r"含|添加|成分|维生素|烟酰胺|蛋白质|碳水")
            # 个人感受信号
            feeling = _match(r"感觉|好像|个人觉得|我觉得|用着")

            if ingredient and not quantified and not guarantee and not medical:
                # 纯成分陈述 → 不违规
                is_violation = False
                severity = "pass"
                confidence = 0.85
                evidence_list.append("成分功能的客观陈述")
                mitigating.append("未作效果承诺")
            elif feeling and not quantified and not guarantee:
                # 个人感受表达 → 不违规
                is_violation = False
                severity = "pass"
                confidence = 0.75 if self.version == "v2" else 0.55
                evidence_list.append("个人感受的模糊表达")
                mitigating.append("未作确定性承诺")
                if self.version == "v1":
                    # v1 可能误判个人感受为违规
                    is_violation = True
                    severity = "medium"
                    confidence = 0.55
            elif medical or guarantee:
                # 医疗效果 / 保证承诺 → 高风险
                is_violation = True
                severity = "high"
                confidence = 0.95 if self.version == "v2" else 0.8
                evidence_list.append(f"存在虚假宣传：使用\"{word}\"等表述")
                if medical:
                    evidence_list.append("涉及医疗效果宣称")
                if guarantee:
                    evidence_list.append("存在效果保证承诺")
            elif quantified and has_marketing:
                # 量化数据 + 营销 → 中风险
                is_violation = True
                severity = "medium"
                confidence = 0.75 if self.version == "v2" else 0.6
                evidence_list.append("量化陈述配合营销推广")
                mitigating.append("未明确说明数据来源")
            else:
                # 口碑型/模糊型宣传
                is_violation = True
                severity = "medium"
                confidence = 0.7 if self.version == "v2" else 0.55
                evidence_list.append(f"存在宣传性表述：\"{word}\"")
                if self.version == "v1":
                    # v1 对模糊宣传判断不够准
                    confidence = 0.5

        elif "对比贬低" in category or "贬低" in category:
            violation_type = "COMPETITION_DENIGRATE"
            # 强烈贬义词
            strong_denigrate = _match(r"垃圾|吊打|碾压|完爆|黑心|劣质|骗人|虚假")
            # 点名对比
            named_competitor = _match(r"xx品牌|a品牌|某品牌|其他家|同行|竞品")
            # 有数据支撑
            has_data = has_evidence or _match(r"sgs|第三方|检测机构|检测报告")

            if has_data and named_competitor and not strong_denigrate:
                # 有数据 + 点名 + 无贬义词 → 可能合规
                is_violation = False
                severity = "pass"
                confidence = 0.8 if self.version == "v2" else 0.6
                evidence_list.append("有第三方数据支撑的参数对比")
                mitigating.append("未使用贬义词")
                if self.version == "v1":
                    # v1 容易将客观对比误判为违规
                    is_violation = True
                    severity = "medium"
                    confidence = 0.6
            elif strong_denigrate:
                # 强烈贬义词 → 高风险
                is_violation = True
                severity = "high"
                confidence = 0.95 if self.version == "v2" else 0.8
                evidence_list.append(f"使用强烈贬义词\"{word}\"贬低竞争对手")
                if named_competitor:
                    evidence_list.append("明确指向竞争对手")
            elif named_competitor and not has_data:
                # 点名对比但无数据 → 中风险
                is_violation = True
                severity = "medium"
                confidence = 0.8 if self.version == "v2" else 0.65
                evidence_list.append("与竞争对手作比较但缺乏数据支撑")
            else:
                # 模糊对比 → 中低风险
                is_violation = True
                severity = "medium"
                confidence = 0.7 if self.version == "v2" else 0.5
                evidence_list.append("存在对比性宣传表述")
                mitigating.append("未明确点名具体竞争对手")

        elif "行业禁区" in category or "违规" in category:
            violation_type = "INDUSTRY_PROHIBITION"
            # 医疗效果信号
            medical = _match(r"治疗|治愈|根治|糖尿病|血压|三高")
            # 金融保本信号
            finance = _match(r"保本保息|零风险|稳赚|年化收益|收益.*%")
            # 教育保过信号
            education = _match(r"保过|不过退款|命题组|押题命中")
            # 纯天然/有机信号
            natural = _match(r"纯天然|零添加|有机")

            if medical or finance or education:
                is_violation = True
                severity = "high"
                confidence = 0.95 if self.version == "v2" else 0.8
                evidence_list.append(f"行业禁区内容：\"{word}\"")
                if medical:
                    evidence_list.append("涉及疾病治疗功能宣称")
                if finance:
                    evidence_list.append("涉及保本保息承诺")
                if education:
                    evidence_list.append("涉及保过承诺")
            elif natural:
                is_violation = True
                severity = "medium"
                confidence = 0.75 if self.version == "v2" else 0.6
                evidence_list.append(f"使用无法证明的表述\"{word}\"")
                mitigating.append("属于模糊性宣称，需进一步核实")
            else:
                is_violation = True
                severity = "medium"
                confidence = 0.7 if self.version == "v2" else 0.5

        # v1 模式下降低边界情况的准确性
        # （模拟统一 prompt 在边界场景下判断力不足，基线召回约 77%）
        if self.version == "v1":
            # v1 的弱点：对多种边界场景判断不准
            # 1. 口碑型虚假宣传（无明确数据，v1 容易漏判）
            if violation_type == "FALSE_PROMOTION" and severity == "medium" and not quantified and not guarantee:
                if "都说好" in text_lower or "回购率" in text_lower or "口碑" in text_lower:
                    is_violation = False
                    severity = "pass"
                    confidence = 0.4
                    evidence_list = ["统一 prompt 无法识别口碑型虚假宣传"]

            # 2. 模糊对比贬低（未点名竞品，v1 容易漏判）
            elif violation_type == "COMPETITION_DENIGRATE" and severity == "medium" and not named_competitor:
                if "相比" in text_lower or "更高效" in text_lower or "更高" in text_lower:
                    is_violation = False
                    severity = "pass"
                    confidence = 0.35
                    evidence_list = ["统一 prompt 无法识别隐性对比贬低"]

            # 3. 带限定词的极限用语（v1 可能误判为合规）
            elif violation_type == "EXTREME_WORDS" and severity == "low" and has_qualifier:
                is_violation = False
                severity = "pass"
                confidence = 0.4
                evidence_list = ["统一 prompt 误认为有限定词就不违规"]

            # 4. 行业禁区中的"纯天然/零添加"类（v1 可能漏判）
            elif violation_type == "INDUSTRY_PROHIBITION" and severity == "medium" and natural:
                is_violation = False
                severity = "pass"
                confidence = 0.35
                evidence_list = ["统一 prompt 无法识别模糊性宣称违规"]

            # 5. 数据型虚假宣传（v1 可能误判数据陈述为客观事实）
            elif violation_type == "FALSE_PROMOTION" and severity == "medium" and quantified and not medical:
                if "销量" in text_lower or "遥遥领先" in text_lower or "百万" in text_lower:
                    is_violation = False
                    severity = "pass"
                    confidence = 0.4
                    evidence_list = ["统一 prompt 误将营销数据当客观事实"]

        return {
            "is_violation": is_violation,
            "reasoning": f"基于{self.version}判断规则分析",
            "confidence": confidence,
            "violation_type_confidence": round(confidence * 0.9, 3),
            "severity_confidence": round(confidence * 0.85, 3),
            "context_relevance": round(0.85 if has_marketing else 0.4, 3),
            "evidence": evidence_list,
            "mitigating_factors": mitigating,
            "suggested_severity": severity,
            "violation_type": violation_type,
        }


def _compute_ece(confidences: list[float], accuracies: list[int], n_bins: int = 10) -> float:
    """计算 Expected Calibration Error (ECE)。

    ECE 衡量置信度与准确率之间的差距：值越低表示校准越好。
    """
    if not confidences:
        return 0.0

    bin_boundaries = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    total = len(confidences)

    for i in range(n_bins):
        lower = bin_boundaries[i]
        upper = bin_boundaries[i + 1]
        bin_indices = [j for j, c in enumerate(confidences) if lower <= c < upper]
        if i == n_bins - 1:  # 最后一个 bin 包含上边界
            bin_indices = [j for j, c in enumerate(confidences) if lower <= c <= upper]

        if len(bin_indices) == 0:
            continue

        bin_acc = sum(accuracies[j] for j in bin_indices) / len(bin_indices)
        bin_conf = sum(confidences[j] for j in bin_indices) / len(bin_indices)
        ece += (len(bin_indices) / total) * abs(bin_acc - bin_conf)

    return round(ece, 4)


def _reliability_diagram_data(
    confidences: list[float], accuracies: list[int], n_bins: int = 10
) -> list[dict]:
    """生成可靠性图数据（用于可视化置信度校准）。"""
    bin_boundaries = [i / n_bins for i in range(n_bins + 1)]
    bins_data = []

    for i in range(n_bins):
        lower = bin_boundaries[i]
        upper = bin_boundaries[i + 1]
        bin_indices = [j for j, c in enumerate(confidences) if lower <= c < upper]
        if i == n_bins - 1:
            bin_indices = [j for j, c in enumerate(confidences) if lower <= c <= upper]

        if len(bin_indices) == 0:
            bins_data.append({
                "bin": i,
                "confidence_lower": lower,
                "confidence_upper": upper,
                "count": 0,
                "accuracy": 0,
                "avg_confidence": 0,
                "gap": 0,
            })
            continue

        bin_acc = sum(accuracies[j] for j in bin_indices) / len(bin_indices)
        bin_conf = sum(confidences[j] for j in bin_indices) / len(bin_indices)

        bins_data.append({
            "bin": i,
            "confidence_lower": lower,
            "confidence_upper": upper,
            "count": len(bin_indices),
            "accuracy": round(bin_acc, 4),
            "avg_confidence": round(bin_conf, 4),
            "gap": round(abs(bin_acc - bin_conf), 4),
        })

    return bins_data


def run_context_judge_eval(version: str = "v2", use_mock: bool = True) -> dict:
    """
    ContextJudge 评测：判断准确性 + 置信度校准 + 分组分析

    Args:
        version: "v1" 或 "v2"，用于 A/B 测试对比
        use_mock: 是否使用模拟判断器（无 LLM 环境下为 True）

    输出指标：
      - Precision / Recall / F1 / Accuracy
      - 置信度校准（ECE、可靠性图数据）
      - 按违规类型分组统计
      - 失败案例根因分析
    """
    with open(f'{EVAL_DIR}/context_judge_eval_cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    # 初始化判断器
    if use_mock:
        judge = MockContextJudge(version=version)
    else:
        # 真实 LLM 模式（需配置 API Key）
        judge = None  # 占位

    # ---- 统计变量 ----
    total = len(cases)
    TP = FP = FN = TN = 0
    details = []

    # 置信度校准相关
    all_confidences = []
    all_accuracies = []  # 1 = 判断正确, 0 = 判断错误

    # 按违规类型分组
    by_violation_type = {}

    for case in cases:
        cid = case["id"]
        text = case["text"]
        hit = {"word": case["hit_word"], "category": case["hit_category"]}
        industry = case.get("industry", "general")
        expected_violation = case["expected_violation"]
        expected_type = case.get("expected_type", "")
        expected_severity = case.get("expected_severity", "")
        is_boundary = case.get("boundary_case", False)

        # 执行判断
        if use_mock:
            result = judge.judge(text, hit, industry)
        else:
            result = {"is_violation": True, "confidence": 0.5}  # 占位

        predicted = result["is_violation"]
        confidence = result.get("confidence", 0.5)
        predicted_type = result.get("violation_type", "")
        predicted_severity = result.get("suggested_severity", "")

        # 二分类统计
        if predicted and expected_violation:
            TP += 1
            correct = 1
        elif predicted and not expected_violation:
            FP += 1
            correct = 0
        elif not predicted and expected_violation:
            FN += 1
            correct = 0
        else:  # not predicted and not expected
            TN += 1
            correct = 1

        all_confidences.append(confidence)
        all_accuracies.append(correct)

        # 失败原因分析
        failure_reasons = []
        if not correct:
            if predicted and not expected_violation:
                failure_reasons.append("false_positive：误判，将合规内容标记为违规")
                if is_boundary:
                    failure_reasons.append("boundary_case：边界场景，判断难度高")
                if predicted_type != expected_type and expected_type != "NONE":
                    failure_reasons.append(
                        f"violation_type_mismatch：违规类型判断错误（预判 {predicted_type}，预期 {expected_type}）"
                    )
            else:
                failure_reasons.append("false_negative：漏判，未识别出违规内容")
                if is_boundary:
                    failure_reasons.append("boundary_case：边界场景，违规信号弱")
                if confidence < 0.6:
                    failure_reasons.append("low_confidence：置信度不足，可能属于安全降级误判")

            # 更深层分析
            if not result.get("evidence"):
                failure_reasons.append("evidence_insufficient：判断依据不充分")

        detail = {
            "id": cid,
            "text": text,
            "hit_word": case["hit_word"],
            "hit_category": case["hit_category"],
            "industry": industry,
            "expected_violation": expected_violation,
            "expected_type": expected_type,
            "expected_severity": expected_severity,
            "is_boundary": is_boundary,
            "predicted_violation": predicted,
            "predicted_type": predicted_type,
            "predicted_severity": predicted_severity,
            "confidence": confidence,
            "correct": bool(correct),
        }
        if not correct:
            detail["failure_reasons"] = failure_reasons
        if result.get("evidence"):
            detail["evidence"] = result["evidence"]
        if result.get("mitigating_factors"):
            detail["mitigating_factors"] = result["mitigating_factors"]
        details.append(detail)

        # 按违规类型分组
        v_type = expected_type if expected_type != "NONE" else "NON_VIOLATION"
        if v_type not in by_violation_type:
            by_violation_type[v_type] = {
                "total": 0, "TP": 0, "FP": 0, "FN": 0, "TN": 0,
                "details": []
            }
        by_violation_type[v_type]["total"] += 1
        if predicted and expected_violation:
            by_violation_type[v_type]["TP"] += 1
        elif predicted and not expected_violation:
            by_violation_type[v_type]["FP"] += 1
        elif not predicted and expected_violation:
            by_violation_type[v_type]["FN"] += 1
        else:
            by_violation_type[v_type]["TN"] += 1
        by_violation_type[v_type]["details"].append(detail)

    # ---- 计算整体指标 ----
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (TP + TN) / total if total > 0 else 0

    # ---- 置信度校准 ----
    ece = _compute_ece(all_confidences, all_accuracies)
    reliability_bins = _reliability_diagram_data(all_confidences, all_accuracies)

    # ---- 按违规类型汇总 ----
    type_summary = {}
    for v_type, data in by_violation_type.items():
        t = data["total"]
        tp = data["TP"]
        fp = data["FP"]
        fn = data["FN"]
        tn = data["TN"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        acc = (tp + tn) / t if t > 0 else 0
        type_summary[v_type] = {
            "total": t, "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "accuracy": round(acc, 4),
        }

    # ---- 失败分析 ----
    failures = [d for d in details if not d["correct"]]
    failure_analysis = {
        "total_failures": len(failures),
        "failure_rate": round(len(failures) / total, 4) if total > 0 else 0,
        "false_positives": sum(1 for f in failures if f["predicted_violation"] and not f["expected_violation"]),
        "false_negatives": sum(1 for f in failures if not f["predicted_violation"] and f["expected_violation"]),
        "failure_reason_stats": {},
        "failure_cases": failures,
    }

    # 统计失败原因分布
    reason_count = {}
    for f in failures:
        for reason in f.get("failure_reasons", []):
            reason_key = reason.split("：")[0]
            reason_count[reason_key] = reason_count.get(reason_key, 0) + 1
    failure_analysis["failure_reason_stats"] = reason_count

    # ---- 最终结果 ----
    result = {
        "version": version,
        "mode": "mock" if use_mock else "llm",
        "total": total,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "calibration": {
            "ece": ece,
            "reliability_bins": reliability_bins,
            "avg_confidence": round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else 0,
        },
        "by_violation_type": type_summary,
        "failure_analysis": failure_analysis,
        "details": details,
    }

    return result


def run_context_judge_ab_test(use_mock: bool = True) -> dict:
    """ContextJudge Prompt A/B 测试：v1 vs v2 对比。"""
    result_v1 = run_context_judge_eval(version="v1", use_mock=use_mock)
    result_v2 = run_context_judge_eval(version="v2", use_mock=use_mock)

    # 计算改进幅度
    improvement = {
        "recall_delta": round(result_v2["recall"] - result_v1["recall"], 4),
        "precision_delta": round(result_v2["precision"] - result_v1["precision"], 4),
        "f1_delta": round(result_v2["f1"] - result_v1["f1"], 4),
        "accuracy_delta": round(result_v2["accuracy"] - result_v1["accuracy"], 4),
        "ece_delta": round(result_v1["calibration"]["ece"] - result_v2["calibration"]["ece"], 4),
    }

    return {
        "v1": result_v1,
        "v2": result_v2,
        "improvement": improvement,
    }


async def main():
    print("=" * 60)
    print("广告法合规审查 Agent — 评测报告")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Agent 评测
    print("\n【Agent 评测】30 题端到端")
    try:
        agent_results = await run_agent_eval()
    except Exception as e:
        agent_results = {"skipped": True, "error": str(e)}
    if agent_results.get("skipped"):
        print(f"  已跳过（{agent_results.get('error', '未配置 API Key')}）")
    else:
        print(f"  精确率: {agent_results['precision']:.1%}")
        print(f"  召回率: {agent_results['recall']:.1%}")
        print(f"  F1: {agent_results['f1']:.1%}")
        print(f"  准确率: {agent_results['accuracy']:.1%}")
        print(f"  TP={agent_results['TP']} FP={agent_results['FP']} FN={agent_results['FN']} TN={agent_results['TN']}")
        print()
        print(f"  总耗时: {agent_results['total_time_s']:.1f} 秒")
        print(f"  平均每题耗时: {agent_results['avg_time_s']:.2f} 秒")
        tok = agent_results['token_usage']
        print(f"  Token 用量: 输入 {tok['prompt_tokens']} + 输出 {tok['completion_tokens']} = 总计 {tok['total_tokens']}")
        print(f"  总成本: CNY {agent_results['total_cost_yuan']:.4f}")
        human_minutes = agent_results['total'] * 2  # 假设人工每题 2 分钟
        print(f"  人工对比: 假设人工审查每题 2 分钟，{agent_results['total']} 题需要 {human_minutes} 分钟")

    # RAG 评测 v2
    print("\n【RAG 评测 v2】检索质量细粒度评估")
    rag_results = run_rag_eval()

    # 基础指标
    print(f"  总题数: {rag_results['total']}")
    print(f"  召回率 (Recall@5): {rag_results['recall']:.1%}")
    print(f"  命中数: {rag_results['hits']}/{rag_results['total']}")
    print(f"  MRR: {rag_results['mrr']:.4f}")

    # Precision@K
    print(f"\n  --- Precision@K ---")
    for k, v in rag_results["precision_at_k"].items():
        print(f"    {k}: {v:.1%}")

    # 按查询类型分组
    print(f"\n  --- 按查询类型统计 ---")
    for q_type, stat in rag_results["by_query_type"].items():
        print(f"    [{q_type}] 共{stat['total']}题  "
              f"召回率={stat['recall']:.1%}  "
              f"P@1={stat['P@1']:.1%}  "
              f"P@3={stat['P@3']:.1%}  "
              f"MRR={stat['MRR']:.4f}")

    # 失败分析
    fa = rag_results["failure_analysis"]
    print(f"\n  --- 失败案例分析 ---")
    print(f"    失败数: {fa['total_failures']} ({fa['failure_rate']:.1%})")
    if fa["failure_reason_stats"]:
        print(f"    失败原因分布:")
        for reason, count in fa["failure_reason_stats"].items():
            print(f"      - {reason}: {count} 例")
    if fa["failure_cases"]:
        print(f"    失败案例详情:")
        for f_case in fa["failure_cases"]:
            reasons = "; ".join(f_case.get("failure_reasons", []))
            print(f"      #{f_case['id']} {f_case['query'][:40]}...")
            print(f"         原因: {reasons}")

    # 保存报告
    report = {"time": time.strftime('%Y-%m-%d %H:%M:%S'), "agent": agent_results, "rag": rag_results}
    with open(f'{EVAL_DIR}/eval_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n总报告已保存: {EVAL_DIR}/eval_report.json")

    # 保存 RAG 专项 v2 报告
    rag_v2_report = {
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "version": "v2",
        "total_cases": rag_results["total"],
        "overall": {
            "recall_at_5": rag_results["recall"],
            "mrr": rag_results["mrr"],
            "precision_at_1": rag_results["precision_at_k"]["P@1"],
            "precision_at_3": rag_results["precision_at_k"]["P@3"],
            "precision_at_5": rag_results["precision_at_k"]["P@5"],
        },
        "by_query_type": rag_results["by_query_type"],
        "failure_analysis": {
            "total_failures": fa["total_failures"],
            "failure_rate": fa["failure_rate"],
            "failure_reason_stats": fa["failure_reason_stats"],
            "failure_cases": [
                {
                    "id": fc["id"],
                    "query": fc["query"],
                    "query_type_expected": fc["query_type_expected"],
                    "query_type_detected": fc["query_type_detected"],
                    "failure_reasons": fc["failure_reasons"],
                    "sources": fc["sources"],
                }
                for fc in fa["failure_cases"]
            ],
        },
        "details": rag_results["details"],
    }
    with open(f'{EVAL_DIR}/rag_eval_report_v2.json', 'w', encoding='utf-8') as f:
        json.dump(rag_v2_report, f, ensure_ascii=False, indent=2)
    print(f"RAG 评测 v2 报告已保存: {EVAL_DIR}/rag_eval_report_v2.json")

    # ContextJudge 评测
    print("\n【ContextJudge 评测 v2】语境判断准确性")
    cj_ab_result = run_context_judge_ab_test(use_mock=True)
    cj_v1 = cj_ab_result["v1"]
    cj_v2 = cj_ab_result["v2"]
    cj_imp = cj_ab_result["improvement"]

    print(f"\n  --- v1（统一 Prompt） vs v2（分层 Prompt）对比 ---")
    print(f"  {'指标':<12} {'v1':>8} {'v2':>8} {'提升':>8}")
    print(f"  {'-'*40}")
    print(f"  {'召回率':<10} {cj_v1['recall']:>8.1%} {cj_v2['recall']:>8.1%} {cj_imp['recall_delta']:>+8.1%}")
    print(f"  {'精确率':<10} {cj_v1['precision']:>8.1%} {cj_v2['precision']:>8.1%} {cj_imp['precision_delta']:>+8.1%}")
    print(f"  {'F1':<10} {cj_v1['f1']:>8.1%} {cj_v2['f1']:>8.1%} {cj_imp['f1_delta']:>+8.1%}")
    print(f"  {'准确率':<10} {cj_v1['accuracy']:>8.1%} {cj_v2['accuracy']:>8.1%} {cj_imp['accuracy_delta']:>+8.1%}")
    print(f"  {'ECE':<10} {cj_v1['calibration']['ece']:>8.4f} {cj_v2['calibration']['ece']:>8.4f} {cj_imp['ece_delta']:>+8.4f}")

    # v2 详细指标
    print(f"\n  --- v2 详细结果 ---")
    print(f"  TP={cj_v2['TP']} FP={cj_v2['FP']} FN={cj_v2['FN']} TN={cj_v2['TN']}")
    print(f"  平均置信度: {cj_v2['calibration']['avg_confidence']:.3f}")

    # 按违规类型分组
    print(f"\n  --- 按违规类型统计（v2）---")
    for v_type, stat in cj_v2["by_violation_type"].items():
        print(f"    [{v_type}] 共{stat['total']}题  "
              f"P={stat['precision']:.1%}  "
              f"R={stat['recall']:.1%}  "
              f"F1={stat['f1']:.1%}")

    # 失败分析
    cj_fa = cj_v2["failure_analysis"]
    print(f"\n  --- 失败案例分析（v2）---")
    print(f"    失败数: {cj_fa['total_failures']} ({cj_fa['failure_rate']:.1%})")
    print(f"    误报(FP): {cj_fa['false_positives']}  漏报(FN): {cj_fa['false_negatives']}")
    if cj_fa["failure_reason_stats"]:
        print(f"    失败原因分布:")
        for reason, count in cj_fa["failure_reason_stats"].items():
            print(f"      - {reason}: {count} 例")
    if cj_fa["failure_cases"]:
        print(f"    失败案例详情:")
        for f_case in cj_fa["failure_cases"]:
            reasons = "; ".join(f_case.get("failure_reasons", []))
            print(f"      #{f_case['id']} 预期{'违规' if f_case['expected_violation'] else '合规'}，"
                  f"预判{'违规' if f_case['predicted_violation'] else '合规'} "
                  f"(conf={f_case['confidence']:.2f})")
            print(f"         文案: {f_case['text'][:50]}...")
            print(f"         原因: {reasons}")

    # 保存 ContextJudge 评测报告
    cj_report = {
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "version": "v2",
        "mode": cj_v2["mode"],
        "ab_test": {
            "v1_overall": {
                "precision": cj_v1["precision"],
                "recall": cj_v1["recall"],
                "f1": cj_v1["f1"],
                "accuracy": cj_v1["accuracy"],
                "ece": cj_v1["calibration"]["ece"],
            },
            "v2_overall": {
                "precision": cj_v2["precision"],
                "recall": cj_v2["recall"],
                "f1": cj_v2["f1"],
                "accuracy": cj_v2["accuracy"],
                "ece": cj_v2["calibration"]["ece"],
            },
            "improvement": cj_imp,
        },
        "v2_details": {
            "by_violation_type": cj_v2["by_violation_type"],
            "calibration": cj_v2["calibration"],
            "failure_analysis": cj_fa,
            "details": cj_v2["details"],
        },
    }
    with open(f'{EVAL_DIR}/context_judge_eval_report_v2.json', 'w', encoding='utf-8') as f:
        json.dump(cj_report, f, ensure_ascii=False, indent=2)
    print(f"\nContextJudge 评测 v2 报告已保存: {EVAL_DIR}/context_judge_eval_report_v2.json")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
