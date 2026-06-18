"""
广告合规审核 Pipeline — CLI 入口

用法:
    python run_pipeline.py parse                # 解析所有数据文件，输出 JSON
    python run_pipeline.py import               # 将解析结果导入 vmem
    python run_pipeline.py search "极限用语"     # 测试三库检索
    python run_pipeline.py stats                # 显示 vmem 统计信息
"""

import argparse
import json
import sys
from pathlib import Path

# 确保 pipeline 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import (
    AD_LAW_FILE,
    PENALTY_CASES_FILE,
    INDUSTRY_RULES_FILE,
    BANNED_WORDS_JSON_FILE,
    WORD_REPLACEMENT_FILE,
    DB_PATH,
    PIPELINE_DIR,
)
from pipeline.parsers import (
    parse_law_articles,
    parse_penalty_cases,
    parse_industry_rules,
    parse_banned_words,
    parse_replacement_map,
    parse_law_articles_teammate,
    parse_banned_words_teammate,
    parse_replacement_map_teammate,
    parse_penalty_cases_teammate,
    parse_industry_rules_teammate,
    TEAMMATE_FILES,
)

# 解析结果输出目录
PARSED_DIR = PIPELINE_DIR / "data" / "parsed"


# ============================================================
# parse 命令
# ============================================================

def cmd_parse():
    """解析 5 类数据文件，将结果保存为 JSON 并打印条目数。"""
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    tasks = [
        # ── 原版数据 ──
        ("ad_law",         parse_law_articles,     AD_LAW_FILE),
        ("penalty_cases",  parse_penalty_cases,    PENALTY_CASES_FILE),
        ("industry_rules", parse_industry_rules,   INDUSTRY_RULES_FILE),
        ("banned_words",   parse_banned_words,     BANNED_WORDS_JSON_FILE),
        ("replacement",    parse_replacement_map,  WORD_REPLACEMENT_FILE),
        # ── 队友版数据 ──
        ("ad_law_new",             parse_law_articles_teammate,       TEAMMATE_FILES["ad_law"]),
        ("penalty_cases_new",      parse_penalty_cases_teammate,      TEAMMATE_FILES["penalty_cases"]),
        ("industry_rules_new",     parse_industry_rules_teammate,     TEAMMATE_FILES["industry_rules"]),
        ("banned_words_new",       parse_banned_words_teammate,       TEAMMATE_FILES["banned_words"]),
        ("replacement_new",        parse_replacement_map_teammate,    TEAMMATE_FILES["replacement"]),
    ]

    print("=" * 60)
    print("Pipeline Parse — 解析数据文件")
    print("=" * 60)

    total = 0
    for name, func, path in tasks:
        try:
            entries = func(path)
            count = len(entries)
            total += count

            # 保存 JSON
            out_file = PARSED_DIR / f"{name}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)

            print(f"  [{name}]  {count} 条  ->  {out_file.name}")
        except Exception as e:
            print(f"  [{name}]  ERROR: {e}")

    print("-" * 60)
    print(f"  合计: {total} 条")
    print(f"  输出目录: {PARSED_DIR}")
    print("=" * 60)


# ============================================================
# import 命令
# ============================================================

def cmd_import():
    """读取 parsed JSON 文件，批量导入 vmem。"""
    from pipeline.storage import VmemStore

    print("=" * 60)
    print("Pipeline Import — 导入 vmem")
    print("=" * 60)

    json_files = sorted(PARSED_DIR.glob("*.json"))
    if not json_files:
        print("  ERROR: parsed 目录为空，请先运行 parse 命令")
        sys.exit(1)

    store = VmemStore(db_path=str(DB_PATH))
    grand_total = 0

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            items = json.load(f)
        count = store.batch_store(items)
        grand_total += count
        print(f"  [{jf.stem}]  导入 {count}/{len(items)} 条")

    store.close()

    print("-" * 60)
    print(f"  合计导入: {grand_total} 条")
    print("=" * 60)


# ============================================================
# search 命令
# ============================================================

def cmd_search(query: str):
    """实例化 ThreeLibRetriever，检索并打印 top-5 结果。"""
    from pipeline.storage import VmemStore
    from pipeline.retrieval import ThreeLibRetriever

    print("=" * 60)
    print(f"Pipeline Search — 查询: {query}")
    print("=" * 60)

    store = VmemStore(db_path=str(DB_PATH))
    retriever = ThreeLibRetriever(store)
    results = retriever.retrieve(query, top_k=5)

    if not results:
        print("  (无结果)")
    else:
        for i, r in enumerate(results, 1):
            lib = r.get("lib", "?")
            key = r.get("key", "?")
            score = r.get("score", 0)
            value = r.get("value", "")
            print(f"\n  [{i}] lib={lib}  key={key}  score={score:.4f}")
            print(f"      {value[:120]}...")

    store.close()
    print(f"\n{'=' * 60}")


# ============================================================
# stats 命令
# ============================================================

def cmd_stats():
    """显示 vmem 三库统计信息。"""
    from pipeline.storage import VmemStore

    print("=" * 60)
    print("Pipeline Stats — vmem 统计信息")
    print("=" * 60)

    store = VmemStore(db_path=str(DB_PATH))
    stats = store.get_stats()
    store.close()

    print(f"\n  总记录数: {stats.get('total', 0)}")
    sources = stats.get("sources", {})
    if sources:
        print("  按来源:")
        for src, cnt in sources.items():
            print(f"    {src}: {cnt}")
    else:
        print("  (数据库为空)")

    print(f"\n{'=' * 60}")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="广告合规审核 Pipeline CLI",
    )
    parser.add_argument(
        "command",
        choices=["parse", "import", "search", "stats"],
        help="要执行的命令: parse / import / search / stats",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="search 命令的查询文本",
    )

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse()
    elif args.command == "import":
        cmd_import()
    elif args.command == "search":
        if not args.query:
            print("ERROR: search 命令需要提供查询文本，例如: python run_pipeline.py search \"极限用语\"")
            sys.exit(1)
        cmd_search(args.query)
    elif args.command == "stats":
        cmd_stats()


if __name__ == "__main__":
    main()
