"""
load_penalty_cases.py — 将处罚案例 markdown 解析并写入 vmem.db 的 items 表
"""
import sys
import sqlite3
import re
import os

DB_PATH = "/Users/saint/Desktop/ad-compliance-agent/pipeline/data/vmem.db"
MD_PATH = "/Users/saint/Desktop/ad-compliance-agent/数据集/处罚案例_队友版.md"

def parse_markdown_cases(md_path: str) -> list[dict]:
    """解析处罚案例 markdown，返回案例列表"""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    cases = []
    # 按表格行解析：| 序号 | 案例 | 违法内容 | 处罚金额 | 处罚机关 |
    pattern = r"\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|"
    for m in re.finditer(pattern, content):
        seq, case_name, violation, penalty, authority = [g.strip() for g in m.groups()]
        # 构造存储 value：包含案例名、违法内容、处罚、机关
        value = f"【{case_name}】违法内容：{violation}。处罚：{penalty}。处罚机关：{authority}。"
        cases.append({
            "key": f"penalty-{seq}-{case_name[:10]}",
            "value": value,
            "source": "penalty_case",
            "tags": "处罚案例",
            "seq": seq,
            "case_name": case_name,
            "penalty": penalty,
            "violation": violation,
        })
    return cases

def load_to_db(cases: list[dict], db_path: str):
    """将案例写入 SQLite items 表"""
    conn = sqlite3.connect(db_path)
    # 确保 items 表存在（FallbackStore 兼容格式）
    conn.execute(
        "CREATE TABLE IF NOT EXISTS items "
        "(key TEXT PRIMARY KEY, value TEXT, source TEXT, tags TEXT)"
    )
    # 清空旧 penalty_case 数据（避免重复）
    conn.execute("DELETE FROM items WHERE source = 'penalty_case'")
    count = 0
    for c in cases:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO items (key, value, source, tags) VALUES (?,?,?,?)",
                (c["key"], c["value"], c["source"], c["tags"])
            )
            count += 1
        except Exception as e:
            print(f"  写入失败 {c['key']}: {e}")
    conn.commit()
    conn.close()
    return count

def main():
    print(f"[1/3] 解析 markdown：{MD_PATH}")
    cases = parse_markdown_cases(MD_PATH)
    print(f"  解析到 {len(cases)} 条处罚案例")

    if not cases:
        print("  未解析到任何案例，请检查 markdown 格式")
        return

    print(f"[2/3] 写入数据库：{DB_PATH}")
    count = load_to_db(cases, DB_PATH)
    print(f"  成功写入 {count} 条")

    print("[3/3] 验证数据...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM items WHERE source = 'penalty_case'")
    total = cur.fetchone()[0]
    cur.execute("SELECT key, value FROM items WHERE source = 'penalty_case' LIMIT 3")
    samples = cur.fetchall()
    conn.close()
    print(f"  验证：DB 中有 {total} 条 penalty_case 记录")
    for k, v in samples:
        print(f"  样本: {k} -> {v[:60]}...")

    print("\n✅ 处罚案例入库完成！")

if __name__ == "__main__":
    main()
