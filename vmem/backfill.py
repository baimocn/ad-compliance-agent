"""
backfill.py - 将所有现有记忆迁移到 vmem 向量库

数据源:
  1. 知识图谱 (mcp__memory__read_graph 数据，硬编码快照)
  2. Evolution 记忆 (SQLite)
  3. 文件记忆 (.md 文件)

直接调用 MemoryVectorStore.store()，不走 MCP。
"""

import os
import sys
import sqlite3
import time
from pathlib import Path

# 将 vmem 模块加入 path
sys.path.insert(0, r"C:\Users\35955\.claude\mcp-servers")
from vmem.store import MemoryVectorStore, EmbeddingEngine


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def migrate_knowledge_graph(store: MemoryVectorStore):
    """迁移知识图谱数据 (硬编码快照，因为 MCP read_graph 不支持 Python 直接调用)"""
    print_header("1. 迁移知识图谱")

    # 知识图谱数据 (来自 mcp__memory__read_graph 的快照)
    entities = [
        {"name": "wechat-scan", "entityType": "project", "observations": [
            "微信聊天数据向量知识库项目", "路径: D:\\Desktop\\wechat-scan",
            "96,793 条消息，134 个会话", "6,765 个向量块，bge-small-zh-v1.5 模型",
            "包含群聊: AI coding The future is here (45720条, 315人)",
            "包含群聊: 63-MiMo订阅会员支持群",
            "知识库已构建完成，向量库 28.5MB，元数据库 14.9MB"
        ]},
        {"name": "kb-core", "entityType": "framework", "observations": [
            "通用向量知识库框架", "路径: C:\\Users\\35955\\.claude\\kb-core\\",
            "支持数据源: 微信JSON / Markdown / 纯文本 / 通用JSON",
            "分块策略: context_window(对话) / fixed_size(文档)",
            "Embedding: bge-small-zh-v1.5, 512维",
            "存储: SQLite向量库 + FTS5全文索引",
            "搜索: 多路融合 (向量45% + 全文30% + 时间衰减10% + 来源匹配15%)",
            "构建命令: python build.py build / update / stats / search"
        ]},
        {"name": "vector-kb-mcp", "entityType": "server", "observations": [
            "MCP服务器，提供向量知识库搜索能力",
            "路径: C:\\Users\\35955\\.claude\\mcp-servers\\vector-kb-server.py",
            "配置: ~/.claude/.mcp.json 中的 vector-kb 条目",
            "工具: search(query, project_path, top_k, session)",
            "工具: stats(project_path)", "工具: list_bases()",
            "自动扫描 Desktop 下所有项目的 knowledge_base/ 目录"
        ]},
        {"name": "07_架构改造实施方案", "entityType": "document", "observations": [
            "路径: D:\\Desktop\\07_架构改造实施方案(1).md",
            "知识库四层架构改造实施方案",
            "核心原则: 只向量化清洗后的内容，不直接向量化原始脏数据",
            "核心原则: 多路融合召回（向量+全文+标签+图谱+证据）",
            "核心原则: 证据链可回源，搜索结果保留来源ID",
            "核心原则: 轻量索引包+按需深读，Agent不默认吞原始正文",
            "核心原则: 候选隔离，新发现先进候选池不直接写正式词典",
            "核心原则: 规则优先LLM补充",
            "分层: 原始数据→清洗融合→分块→向量化→存储→多路召回→按需深读"
        ]},
        {"name": "用户", "entityType": "person", "observations": [
            "D:\\Desktop 下有多个项目", "关注 AI coding 相关技术",
            "在 AI coding: The future is here 微信群中",
            "在 63-MiMo订阅会员支持群 中",
            "希望知识库框架能复用到新项目", "关注持久化记忆功能"
        ]},
        {"name": "auto-memory-system", "entityType": "system", "observations": [
            "自动记忆系统设计",
            "三层保障: CLAUDE.md指令 + autoMemoryEnabled + SessionEnd hook",
            "CLAUDE.md (~/.claude/CLAUDE.md) 定义写入时机和规则",
            "autoMemoryEnabled=true 自动保存文件记忆",
            "SessionEnd hook 触发 memory-sync.py 同步脚本",
            "知识图谱写入只能通过 Claude 对话中调用 MCP 工具完成",
            "hooks 无法直接调用 MCP 工具，这是当前架构的限制",
            "核心解法: CLAUDE.md 指令足够强，让 Claude 养成自动写入的习惯"
        ]},
        {"name": "项目进度", "entityType": "状态", "observations": [
            "171道题目已从7个MD文件解析到chapterBank.ts",
            "所有题目的answer正确填充，选项isCorrect正确标记",
            "包含106道选择题(单选+多选)和65道判断题",
            "文件为UTF-8编码，中文内容正确",
            "下一步：将chapterBank集成到练习页面，替换旧的数据文件",
            "已从7个MD文件解析171道题目到chapterBank.ts",
            "文件编码为UTF-8，中文内容字节正确",
            "chapterBank已集成到index.ts，替换了旧的choice.ts和true-false.ts",
            "构建成功，0个TypeScript错误"
        ]},
        {"name": "chapterBank数据", "entityType": "数据", "observations": [
            "位于botany-learn/src/data/questions/chapterBank.ts",
            "包含Ch1-Ch8共7个章节(实际存储为chapters 1,2,4,5,6,7,8)",
            "单选题格式：type='choice'，answer格式'C:有光反应时'",
            "多选题格式：type='choice'，answer格式'AD:C4植物; C3植物'",
            "判断题格式：type='true-false'，answer格式'对'或'错'",
            "import路径已修正为../../types/question",
            "文件共2121行，171道题",
            "多选题答案格式：'AD:C4植物; C3植物'",
            "isTrue和isCorrect字段正确标记"
        ]},
        {"name": "baimo-studio", "entityType": "project", "observations": [
            "baimo Studio 是基于 Agnes AI 的图片与视频生成平台",
            "GitHub 仓库: https://github.com/baimocn/baimo-studio",
            "技术栈: Next.js 16 + React 19 + FastAPI + SQLAlchemy",
            "支持文生图、图生图、多图合成、文生视频、图生视频等全链路 AI 创作",
            "可部署为 Docker 容器、本地运行或打包为桌面客户端 (.exe)",
            "许可证: GNU General Public License v3.0"
        ]},
        {"name": "xi-opencode", "entityType": "project", "observations": [
            "tests/test_cov_boost_utils.py 覆盖 decorators.py、security.py、redis_client.py、jwt.py、monitoring.py、prometheus.py、audit_logger.py、structured_logging.py 共 8 个模块，105 个测试全部通过。"
        ]},
        {"name": "claude-code-path-format", "entityType": "lesson", "observations": [
            "Claude Code settings.json 中所有 bash 命令的路径必须用正斜杠 / 不能用反斜杠 \\",
            "PowerShell 的 ConvertTo-Json 会把路径 C:\\Users 变成 C:\\\\Users（双反斜杠），bash 无法识别",
            "正确写法: bash C:/Users/xxx/.claude/script.sh",
            "错误写法: bash C:\\Users\\xxx\\.claude\\script.sh",
            "修复方法: 在 PowerShell 中用 .Replace('\\', '/') 转换路径后再写入 JSON",
            "这个错误已经犯了两次，必须永远记住"
        ]},
    ]

    relations = [
        {"from": "wechat-scan", "to": "kb-core", "relationType": "uses_framework"},
        {"from": "vector-kb-mcp", "to": "wechat-scan", "relationType": "can_search"},
        {"from": "kb-core", "to": "07_架构改造实施方案", "relationType": "inspired_by"},
        {"from": "vector-kb-mcp", "to": "kb-core", "relationType": "depends_on"},
        {"from": "用户", "to": "wechat-scan", "relationType": "owns"},
        {"from": "用户", "to": "kb-core", "relationType": "requested"},
        {"from": "用户", "to": "vector-kb-mcp", "relationType": "requested"},
        {"from": "auto-memory-system", "to": "wechat-scan", "relationType": "manages"},
        {"from": "auto-memory-system", "to": "kb-core", "relationType": "manages"},
        {"from": "用户", "to": "auto-memory-system", "relationType": "requested"},
    ]

    total = len(entities) + len(relations)
    done = 0

    # 迁移实体
    print(f"\n  迁移 {len(entities)} 个实体...")
    for e in entities:
        key = e["name"]
        value = "\n".join(e["observations"])
        tags = e["entityType"]
        ok = store.store(key=key, value=value, source="knowledge-graph", level="long", tags=tags)
        done += 1
        status = "OK" if ok else "FAIL"
        print(f"  [{done}/{total}] entity: {key} ({tags}) -> {status}")

    # 迁移关系
    print(f"\n  迁移 {len(relations)} 条关系...")
    for r in relations:
        key = f"rel:{r['from']}:{r['to']}"
        value = f"{r['from']} --[{r['relationType']}]--> {r['to']}"
        ok = store.store(key=key, value=value, source="knowledge-graph", level="long", tags="relation")
        done += 1
        status = "OK" if ok else "FAIL"
        print(f"  [{done}/{total}] relation: {key} -> {status}")

    print(f"\n  知识图谱迁移完成: {done} 条记录")


def migrate_evolution_db(store: MemoryVectorStore):
    """迁移 Evolution 记忆数据库"""
    print_header("2. 迁移 Evolution 记忆")

    db_path = r"C:\Users\35955\.claude\memory\evolution_memory.db"
    if not os.path.exists(db_path):
        print(f"  跳过: {db_path} 不存在")
        return

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT key, value, level, created_at, metadata FROM memories").fetchall()
    conn.close()

    print(f"  找到 {len(rows)} 条记录")

    for i, row in enumerate(rows, 1):
        key, value, level, created_at, metadata = row
        # 前缀避免与其他源冲突
        store_key = f"evo:{key}"
        ok = store.store(
            key=store_key,
            value=value,
            source="evolution",
            level=level or "",
            tags="evolution-memory",
        )
        status = "OK" if ok else "FAIL"
        print(f"  [{i}/{len(rows)}] {store_key} -> {status}")

    print(f"\n  Evolution 记忆迁移完成: {len(rows)} 条记录")


def migrate_file_memories(store: MemoryVectorStore):
    """迁移文件记忆 (.md 文件)"""
    print_header("3. 迁移文件记忆")

    mem_dir = Path(r"C:\Users\35955\.claude\projects\C--Users-35955\memory")
    if not mem_dir.exists():
        print(f"  跳过: {mem_dir} 不存在")
        return

    md_files = [f for f in mem_dir.glob("*.md") if f.name.lower() != "memory.md"]
    print(f"  找到 {len(md_files)} 个记忆文件 (排除 MEMORY.md)")

    for i, fp in enumerate(md_files, 1):
        content = fp.read_text(encoding="utf-8")
        store_key = f"file:{fp.stem}"
        # 从 frontmatter 提取 type 作为 tag
        tags = "file-memory"
        if content.startswith("---"):
            try:
                fm_end = content.index("---", 3)
                frontmatter = content[3:fm_end]
                for line in frontmatter.split("\n"):
                    if line.strip().startswith("type:"):
                        tags = f"file-memory,{line.split(':',1)[1].strip()}"
                        break
            except ValueError:
                pass

        ok = store.store(
            key=store_key,
            value=content,
            source="file-memory",
            level="long",
            tags=tags,
        )
        status = "OK" if ok else "FAIL"
        print(f"  [{i}/{len(md_files)}] {store_key} ({fp.name}) -> {status}")

    print(f"\n  文件记忆迁移完成: {len(md_files)} 条记录")


def main():
    print_header("vmem 全量迁移脚本")
    print(f"  启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  模型路径: C:\\Users\\35955\\bge-small-zh-v1.5")
    print(f"  数据库: C:\\Users\\35955\\.claude\\memory\\vmem.db")

    start = time.time()

    # 初始化 store (会自动创建目录和表)
    engine = EmbeddingEngine(model_path=r"C:\Users\35955\bge-small-zh-v1.5")
    store = MemoryVectorStore(embedding_engine=engine)

    # 执行三类迁移
    migrate_knowledge_graph(store)
    migrate_evolution_db(store)
    migrate_file_memories(store)

    # 统计
    print_header("迁移统计")
    stats = store.get_stats()
    print(f"  总记录数: {stats['total']}")
    print(f"  来源分布: {stats['sources']}")
    print(f"  级别分布: {stats['levels']}")
    print(f"  耗时: {time.time() - start:.1f}s")
    print(f"  数据库: {stats['db_path']}")

    store.close()
    print("\n  迁移完成!")


if __name__ == "__main__":
    main()
