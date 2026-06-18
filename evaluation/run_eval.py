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

    for case in cases:
        req = ReviewRequest(text=case["text"], industry=Industry(case.get("industry", "general")))
        resp = await agent_inst.review(req)

        predicted = resp.status == "violation_found"
        actual = case["expected_violation"]

        if predicted and actual: results["TP"] += 1
        elif predicted and not actual: results["FP"] += 1
        elif not predicted and actual: results["FN"] += 1
        else: results["TN"] += 1

    agent_inst.close()

    precision = results["TP"] / (results["TP"] + results["FP"]) if (results["TP"] + results["FP"]) > 0 else 0
    recall = results["TP"] / (results["TP"] + results["FN"]) if (results["TP"] + results["FN"]) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (results["TP"] + results["TN"]) / results["total"]

    results.update({"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy})
    return results


def run_rag_eval():
    """RAG 评测：15 题检索质量"""
    import config
    from storage import VmemStore
    from retrieval import ThreeLibRetriever

    with open(f'{EVAL_DIR}/rag_eval_cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    store = VmemStore(str(config.DB_PATH))
    retriever = ThreeLibRetriever(store)

    hits = 0
    details = []
    for case in cases:
        results = retriever.retrieve(case["query"], top_k=5)
        all_text = " ".join([r.get("value", "") for r in results])
        sources = [r.get("source", "") for r in results]

        keyword_hit = all(kw in all_text for kw in case["expected_keywords"])
        source_hit = case["expected_source"] in sources
        passed = keyword_hit or source_hit
        if passed: hits += 1

        details.append({"id": case["id"], "query": case["query"], "passed": passed, "sources": sources})

    store.close()
    return {"hits": hits, "total": len(cases), "recall": hits / len(cases), "details": details}


async def main():
    print("=" * 60)
    print("广告法合规审查 Agent — 评测报告")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Agent 评测
    print("\n【Agent 评测】30 题端到端")
    agent_results = await run_agent_eval()
    if agent_results.get("skipped"):
        print("  已跳过（未配置 API Key）")
    else:
        print(f"  精确率: {agent_results['precision']:.1%}")
        print(f"  召回率: {agent_results['recall']:.1%}")
        print(f"  F1: {agent_results['f1']:.1%}")
        print(f"  准确率: {agent_results['accuracy']:.1%}")
        print(f"  TP={agent_results['TP']} FP={agent_results['FP']} FN={agent_results['FN']} TN={agent_results['TN']}")

    # RAG 评测
    print("\n【RAG 评测】15 题检索质量")
    rag_results = run_rag_eval()
    print(f"  召回率: {rag_results['recall']:.1%}")
    print(f"  命中: {rag_results['hits']}/{rag_results['total']}")

    # 保存报告
    report = {"time": time.strftime('%Y-%m-%d %H:%M:%S'), "agent": agent_results, "rag": rag_results}
    with open(f'{EVAL_DIR}/eval_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {EVAL_DIR}/eval_report.json")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
