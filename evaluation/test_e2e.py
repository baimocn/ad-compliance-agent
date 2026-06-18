"""端到端集成测试 — 直接调用 Agent 函数"""
import sys
import asyncio
import time
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

async def test_banned_word_matcher():
    """测试1：禁用词匹配"""
    from tools.banned_word import BannedWordMatcher
    import config

    matcher = BannedWordMatcher(config.BANNED_WORDS_PATH)

    cases = [
        ("全网最低价", True, "最低"),
        ("这款产品很好用", False, None),
        ("100%有效", True, "100%"),
        ("国家级品质", True, "国家级"),
        ("限时优惠", False, None),
        ("买到就是赚到", True, "赚到"),
        ("第一品牌", True, "第一"),
        ("优质产品", False, None),
    ]

    passed = 0
    for text, should_match, keyword in cases:
        hits = matcher.match(text)
        matched = len(hits) > 0
        status = "PASS" if matched == should_match else "FAIL"
        if status == "PASS": passed += 1
        print(f"  {status}: '{text}' -> matched={matched} (expected={should_match})")

    print(f"\n禁用词匹配测试: {passed}/{len(cases)} 通过\n")
    return passed == len(cases)


async def test_review_pipeline():
    """测试2：完整审查流程（需要 DeepSeek API Key）"""
    from agent import ComplianceAgent
    from schemas import ReviewRequest, Industry, RiskLevel
    import config

    if not config.LLM_API_KEY or config.LLM_API_KEY == "sk-your-key-here":
        print("  SKIP: 未配置 DEEPSEEK_API_KEY，跳过 LLM 测试\n")
        return True

    agent_inst = ComplianceAgent(config)

    test_texts = [
        {
            "text": "全网最低价，买到就是赚到！",
            "expected_risk": ["high", "medium"],
            "desc": "明显的极限用语+虚假宣传"
        },
        {
            "text": "本产品采用优质原料，口感醇厚",
            "expected_risk": ["pass", "low"],
            "desc": "正常的产品描述"
        },
        {
            "text": "100%有效，根治痘痘，永不反弹",
            "expected_risk": ["high"],
            "desc": "严重的虚假宣传"
        },
    ]

    passed = 0
    for case in test_texts:
        req = ReviewRequest(text=case["text"], industry=Industry.GENERAL)
        try:
            resp = await agent_inst.review(req)
            status = "PASS" if resp.overall_risk.value in case["expected_risk"] else "FAIL"
            if status == "PASS": passed += 1
            print(f"  {status}: {case['desc']}")
            print(f"    输入: {case['text'][:30]}...")
            print(f"    风险: {resp.overall_risk.value} (expected: {case['expected_risk']})")
            print(f"    违规数: {len(resp.violations)}")
        except Exception as e:
            print(f"  FAIL: {case['desc']} -> {e}")

    agent_inst.close()
    print(f"\n审查流程测试: {passed}/{len(test_texts)} 通过\n")
    return passed == len(test_texts)


async def test_rag_retrieval():
    """测试3：RAG 检索质量"""
    from storage import VmemStore
    from retrieval import ThreeLibRetriever

    import config
    store = VmemStore(str(config.DB_PATH))
    retriever = ThreeLibRetriever(store)

    cases = [
        {
            "query": "广告法 不得使用",
            "expected_source": "ad_law",
            "desc": "应检索到广告法条文"
        },
        {
            "query": "全网最低价 罚款",
            "expected_source": "penalty_case",
            "desc": "应检索到处罚案例"
        },
        {
            "query": "食品广告 禁区",
            "expected_source": "industry_rule",
            "desc": "应检索到行业规则"
        },
    ]

    passed = 0
    for case in cases:
        results = retriever.retrieve(case["query"], top_k=5)
        sources = [r.get("source", "") for r in results]
        found = case["expected_source"] in sources
        status = "PASS" if found else "FAIL"
        if status == "PASS": passed += 1
        print(f"  {status}: {case['desc']}")
        print(f"    查询: '{case['query']}'")
        print(f"    返回来源: {sources}")

    store.close()
    print(f"\nRAG 检索测试: {passed}/{len(cases)} 通过\n")
    return passed == len(cases)


async def main():
    print("=" * 60)
    print("广告法合规审查 Agent — 端到端集成测试")
    print("=" * 60)
    print()

    results = []

    print("【测试1】禁用词匹配")
    results.append(await test_banned_word_matcher())

    print("【测试2】审查流程（LLM）")
    results.append(await test_review_pipeline())

    print("【测试3】RAG 检索质量")
    results.append(await test_rag_retrieval())

    print("=" * 60)
    total = sum(results)
    print(f"总结果: {total}/{len(results)} 测试组通过")
    if total == len(results):
        print("[OK] 全部通过！")
    else:
        print("[WARN] 部分测试未通过，请检查上方日志")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
