"""
广告法合规审查 Agent — 主管线入口

用法:
  python run_pipeline.py                 # 解析 + 入库 + 打印统计
  python run_pipeline.py --eval          # 仅跑评测 (需要 agent_fn)
  python run_pipeline.py --rebuild       # 重建索引
  python run_pipeline.py --test "你的广告文案"  # 试查一条
"""
import sys
import json
import logging
from pathlib import Path

# 添加 pipeline 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, EvalConfig
from parsers import parse_all
from storage import VmemStore, store_all_parsed, rebuild_index
from retrieval import ThreeLibRetriever, build_retrieval_context, search_ad_compliance
from feedback import FeedbackPipeline, compute_quality_metrics
from evaluation import (
    build_agent_eval_dataset, build_rag_eval_dataset,
    AgentEvaluator, RAGEvaluator,
    format_eval_report, save_eval_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def run_pipeline(rebuild: bool = False):
    """
    运行完整的数据管线: 解析 → 入库 → 统计。
    """
    print("=" * 60)
    print("  广告法合规审查 Agent — 数据管线")
    print("=" * 60)
    print()

    # 1. 解析
    print("[1/3] 解析数据文件...")
    all_chunks = parse_all()

    total = 0
    for name, chunks in all_chunks.items():
        count = len(chunks)
        total += count
        print(f"  {name:15s}: {count:>4d} chunks")
        if chunks:
            sample = chunks[0]
            print(f"    sample key : {sample['key']}")
            print(f"    sample tags: {sample['tags'][:5]}")
    print(f"  {'TOTAL':15s}: {total:>4d} chunks")
    print()

    # 2. 入库
    print("[2/3] 写入 vmem...")
    store = VmemStore()

    if rebuild:
        results = rebuild_index(store, all_chunks)
    else:
        results = store_all_parsed(store, all_chunks)

    for lib_name, result in results.items():
        print(f"  {lib_name:15s}: {result['success']}/{result['total']} stored")
    print()

    # 3. 统计
    print("[3/3] 存储统计:")
    stats = store.get_stats()
    print(f"  总条目: {stats['total_stored']}")
    for source, count in stats['by_source'].items():
        print(f"  {source:20s}: {count}")
    print()

    return store, all_chunks


def test_retrieve(store: VmemStore, query: str):
    """试查一条。"""
    print(f"\n{'='*60}")
    print(f"  试查: {query}")
    print(f"{'='*60}\n")

    context = search_ad_compliance(store, query, top_k=5)
    print(context)


def run_eval_demo():
    """
    跑评测数据集 (不需要真实 Agent，用模拟函数演示)。
    """
    print("=" * 60)
    print("  评测数据集概览")
    print("=" * 60)
    print()

    # Agent 评测
    agent_cases = build_agent_eval_dataset()
    print(f"Agent 评测: {len(agent_cases)} 题")
    categories = {}
    for c in agent_cases:
        categories[c.category] = categories.get(c.category, 0) + 1
    for cat, count in categories.items():
        print(f"  {cat}: {count} 题")
    print()

    # RAG 评测
    rag_cases = build_rag_eval_dataset()
    print(f"RAG 评测: {len(rag_cases)} 题")
    for c in rag_cases:
        print(f"  {c.id}: {c.query[:40]}...")
    print()

    # 模拟评测 (mock agent)
    def mock_agent_fn(input_text: str) -> dict:
        """模拟 Agent 输出。"""
        issues = []
        risk = "low"
        refs = []

        # 简单关键词检测
        danger_words = [
            "最", "第一", "唯一", "顶级", "绝对", "100%", "国家级",
            "全网", "史上", "永不", "根治", "治愈", "保本", "稳赚",
            "保过", "包过", "风水",
        ]
        for word in danger_words:
            if word in input_text:
                issues.append(f"检测到敏感词: {word}")

        if len(issues) >= 3:
            risk = "critical"
        elif len(issues) >= 2:
            risk = "high"
        elif len(issues) >= 1:
            risk = "medium"

        return {
            "issues": issues,
            "risk_level": risk,
            "suggestions": [f"建议删除或替换敏感表述"] if issues else [],
            "references": ["广告法第九条"] if issues else [],
        }

    print("[Mock Agent 评测]")
    agent_eval = AgentEvaluator(mock_agent_fn)
    agent_report = agent_eval.evaluate_all(agent_cases)
    print(format_eval_report(agent_report))

    # 保存报告
    eval_dir = DATA_DIR / "eval_results"
    save_eval_report(agent_report, eval_dir / "agent_eval_report.json")
    print(f"\n报告已保存: {eval_dir / 'agent_eval_report.json'}")


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--eval" in args:
        run_eval_demo()
    elif "--test" in args:
        idx = args.index("--test")
        query = args[idx + 1] if idx + 1 < len(args) else "全网销量第一的化妆品"
        store, _ = run_pipeline()
        test_retrieve(store, query)
    elif "--rebuild" in args:
        run_pipeline(rebuild=True)
    else:
        run_pipeline()
        run_eval_demo()
