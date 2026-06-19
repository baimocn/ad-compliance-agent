export const meta = {
  name: 'fix-hackathon-p0p1',
  description: '修复广告法合规审查 Agent 的 P0/P1 问题：硬编码路径、行业枚举、反馈后端、统计面板、评测运行、README 更新',
  phases: [
    { title: 'P0 路径修复', detail: '修复所有硬编码绝对路径' },
    { title: 'P0 前后端联调', detail: '修复行业枚举不匹配 + 实现反馈后端' },
    { title: 'P0 评测运行', detail: '运行 Agent 评测拿到准确率数据' },
    { title: 'P1 统计面板', detail: '实现 /api/stats 真实数据' },
    { title: 'P1 文档更新', detail: '更新 README 和评测报告' },
  ],
}

const PROJECT = 'D:/Desktop/黑客松'

// =======================================================================
// Phase 1: P0 路径修复 — 修复所有硬编码绝对路径
// =======================================================================

phase('P0 路径修复')

// 1a. 修复 backend/agent.py
await agent(`Fix hardcoded paths in ${PROJECT}/backend/agent.py

Replace the 3 sys.path.insert lines at the top:
\`\`\`python
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
sys.path.insert(0, 'D:/Desktop/黑客松/pipeline')
sys.path.insert(0, 'D:/Desktop/黑客松')
\`\`\`

With pathlib-based relative paths:
\`\`\`python
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT))
\`\`\`

Also fix backend/config.py - replace all hardcoded D:/Desktop/黑客松 paths with Path-based relative paths using PROJECT_ROOT = Path(__file__).resolve().parent.parent.

backend/config.py should become:
\`\`\`python
import os
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DB_PATH = os.getenv("VMEM_DB_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "vmem.db"))
BANNED_WORDS_PATH = os.getenv("BANNED_WORDS_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "禁用词" / "banned_words.json"))
REPLACEMENT_PATH = os.getenv("REPLACEMENT_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "parsed" / "replacement.json"))
\`\`\`

Read each file first, then use Edit to make the changes.`, {
  label: 'fix-agent-config-paths',
  phase: 'P0 路径修复',
})

// 1b. 修复 backend/main.py
await agent(`Fix hardcoded paths in ${PROJECT}/backend/main.py

Read the file first. Replace:
\`\`\`python
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
sys.path.insert(0, 'D:/Desktop/黑客松/pipeline')
\`\`\`

With:
\`\`\`python
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
sys.path.insert(0, str(_PROJECT / 'pipeline'))
\`\`\`

Use Edit tool.`, {
  label: 'fix-main-paths',
  phase: 'P0 路径修复',
})

// 1c. 修复 backend/tools/*.py
await agent(`Fix hardcoded paths in all backend/tools/ files.

Read and fix these 4 files:
1. ${PROJECT}/backend/tools/banned_word.py - line 4: sys.path.insert(0, 'D:/Desktop/黑客松/backend')
2. ${PROJECT}/backend/tools/context_judge.py - line 2: sys.path.insert(0, 'D:/Desktop/黑客松/backend')
3. ${PROJECT}/backend/tools/regulation_rag.py - lines 3-4: two sys.path.insert with D:/Desktop/黑客松
4. ${PROJECT}/backend/tools/rewrite.py - line 4: sys.path.insert(0, 'D:/Desktop/黑客松/backend')

For each file, replace the hardcoded D:/Desktop/黑客松 paths with path-based approach:
\`\`\`python
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
\`\`\`

For regulation_rag.py which has TWO path inserts, replace both. Read each file first, then use Edit.`, {
  label: 'fix-tools-paths',
  phase: 'P0 路径修复',
})

// 1d. 修复 evaluation 和 test 文件
await agent(`Fix hardcoded paths in evaluation and test files.

Read and fix these files:
1. ${PROJECT}/evaluation/run_eval.py - has hardcoded EVAL_DIR = 'D:/Desktop/黑客松/evaluation' and sys.path.insert lines
2. ${PROJECT}/evaluation/test_e2e.py - has hardcoded sys.path.insert lines and vmem db path

For run_eval.py, replace:
\`\`\`python
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
sys.path.insert(0, 'D:/Desktop/黑客松/pipeline')
sys.path.insert(0, 'D:/Desktop/黑客松')

EVAL_DIR = 'D:/Desktop/黑客松/evaluation'
\`\`\`

With:
\`\`\`python
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT))

EVAL_DIR = str(_PROJECT / 'evaluation')
\`\`\`

Also fix the hardcoded DB path in run_rag_eval:
\`\`\`python
store = VmemStore('D:/Desktop/黑客松/pipeline/data/vmem.db')
\`\`\`
→
\`\`\`python
import config
store = VmemStore(str(config.DB_PATH))
\`\`\`
(config is from pipeline.config)

For test_e2e.py, fix the same pattern.

Read each file first, then use Edit.`, {
  label: 'fix-eval-paths',
  phase: 'P0 路径修复',
})

// 1e. 修复 pipeline/storage.py
await agent(`Fix hardcoded path in ${PROJECT}/pipeline/storage.py

Read the file. Replace:
\`\`\`python
sys.path.insert(0, 'D:/Desktop/黑客松')
\`\`\`

With:
\`\`\`python
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
\`\`\`

Use Edit tool.`, {
  label: 'fix-storage-paths',
  phase: 'P0 路径修复',
})

// 1f. 验证路径修复
await agent(`Verify all hardcoded paths are fixed.

Run these commands to check:
1. grep for any remaining D:/Desktop in the backend/ and evaluation/ directories
2. Run: python -c "import sys; sys.path.insert(0, 'D:/Desktop/黑客松/backend'); sys.path.insert(0, 'D:/Desktop/黑客松/pipeline'); from agent import ComplianceAgent; print('import OK')"

Working directory: ${PROJECT}`, {
  label: 'verify-paths',
  phase: 'P0 路径修复',
})


// =======================================================================
// Phase 2: P0 前后端联调 — 修复行业枚举 + 实现反馈后端
// =======================================================================

phase('P0 前后端联调')

// 2a. 修复前端行业枚举
await agent(`Fix the industry enum mismatch in the frontend review page.

Read ${PROJECT}/frontend/src/app/review/page.tsx first.

The INDUSTRIES constant (around line 63-71) has wrong values that don't match the backend:
- "cosmetics" should be "cosmetic"
- "realestate" should be "real_estate"
- "other" should be "general"
- Missing "general" option

Replace the INDUSTRIES constant with:
\`\`\`typescript
const INDUSTRIES = [
  { value: "general", label: "通用" },
  { value: "food", label: "食品饮料" },
  { value: "cosmetic", label: "化妆品" },
  { value: "medicine", label: "医疗健康" },
  { value: "education", label: "教育培训" },
  { value: "finance", label: "金融理财" },
  { value: "real_estate", label: "房地产" },
  { value: "ecommerce", label: "电子商务" },
]
\`\`\`

Use Edit tool. Make sure to read the file first.`, {
  label: 'fix-frontend-enum',
  phase: 'P0 前后端联调',
})

// 2b. 实现反馈后端（反馈存储到 SQLite）
await agent(`Implement the feedback backend — store review and feedback data in SQLite.

Read these files first:
1. ${PROJECT}/backend/main.py
2. ${PROJECT}/backend/schemas.py

Then implement a simple SQLite-based storage for reviews and feedback.

**Step 1**: Create ${PROJECT}/backend/store.py with a ReviewStore class:
\`\`\`python
"""审查记录存储 — SQLite"""
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional

class ReviewStore:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "pipeline" / "data" / "review.db")
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    overall_risk TEXT NOT NULL,
                    violation_count INTEGER DEFAULT 0,
                    violations_json TEXT DEFAULT '[]',
                    industry TEXT DEFAULT 'general',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id TEXT NOT NULL,
                    violation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    replacement TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
                )
            """)
            conn.commit()

    def save_review(self, review_id: str, text: str, status: str, overall_risk: str,
                    violation_count: int, violations: list, industry: str = "general"):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?)",
                (review_id, text, status, overall_risk, violation_count,
                 json.dumps(violations, ensure_ascii=False), industry,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def save_feedback(self, review_id: str, violation_id: str, action: str,
                      replacement: Optional[str] = None):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO feedback (review_id, violation_id, action, replacement, created_at) VALUES (?,?,?,?,?)",
                (review_id, violation_id, action, replacement,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def get_stats(self) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            total_reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            total_violations = conn.execute("SELECT SUM(violation_count) FROM reviews").fetchone()[0] or 0

            # By category
            rows = conn.execute(
                "SELECT violations_json FROM reviews WHERE violation_count > 0"
            ).fetchall()
            category_counts = {}
            severity_counts = {"high": 0, "medium": 0, "low": 0, "pass": 0}
            for row in rows:
                violations = json.loads(row[0])
                for v in violations:
                    cat = v.get("category", "未知")
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    sev = v.get("severity", "low")
                    if sev in severity_counts:
                        severity_counts[sev] += 1

            # Recent reviews
            recent = conn.execute(
                "SELECT review_id, substr(text,1,30) as text, status, overall_risk, violation_count "
                "FROM reviews ORDER BY created_at DESC LIMIT 10"
            ).fetchall()

            return {
                "total_reviews": total_reviews,
                "total_violations": total_violations,
                "violation_by_category": [{"category": k, "count": v} for k, v in category_counts.items()],
                "violation_by_severity": [{"severity": k, "count": v} for k, v in severity_counts.items()],
                "recent_reviews": [
                    {"reviewId": r[0], "text": r[1], "status": r[2],
                     "overallRisk": r[3], "violationCount": r[4]}
                    for r in recent
                ],
            }

    def close(self):
        pass
\`\`\`

**Step 2**: Edit ${PROJECT}/backend/main.py to:
1. Import ReviewStore
2. Create a global review_store instance
3. In the /api/review endpoint, after getting the response, call review_store.save_review()
4. Replace the /api/feedback endpoint to actually store feedback
5. Replace the /api/stats endpoint to return real data from review_store

The main.py should look like this after editing (read it first to get the exact content):
- Add: \`from store import ReviewStore\`
- Add global: \`review_store = None\`
- In startup: \`review_store = ReviewStore()\`
- In /api/review: add \`review_store.save_review(...)\` after getting the response
- In /api/feedback: call \`review_store.save_feedback(...)\`
- In /api/stats: return \`review_store.get_stats()\`

Read main.py first, then use Edit tool to make the changes.`, {
  label: 'implement-feedback-stats',
  phase: 'P0 前后端联调',
})

// 2c. 验证后端启动
await agent(`Verify the backend can start without errors.

Working directory: ${PROJECT}

Run: python -c "
import sys
sys.path.insert(0, 'backend')
sys.path.insert(0, 'pipeline')
import config
print('API_KEY set:', bool(config.LLM_API_KEY and config.LLM_API_KEY != 'sk-your-key-here'))
print('DB_PATH:', config.DB_PATH)
from store import ReviewStore
rs = ReviewStore()
print('ReviewStore OK')
stats = rs.get_stats()
print('Stats:', stats)
print('ALL OK')
"
`, {
  label: 'verify-backend-startup',
  phase: 'P0 前后端联调',
})


// =======================================================================
// Phase 3: P0 评测运行 — 运行 Agent 评测拿到准确率
// =======================================================================

phase('P0 评测运行')

// 3a. 运行端到端测试
await agent(`Run the end-to-end integration tests to verify the basic pipeline works.

Working directory: ${PROJECT}

Run: python evaluation/test_e2e.py

This tests:
1. Banned word matcher (deterministic, no API needed)
2. Full review pipeline (needs DeepSeek API key)
3. RAG retrieval (no API needed)

Report the results. If any test fails, analyze the error and fix it.
The API key is configured in .env file.`, {
  label: 'run-e2e-tests',
  phase: 'P0 评测运行',
})

// 3b. 运行 Agent 评测（30题）
await agent(`Run the Agent evaluation (30 questions) to get precision/recall/F1 scores.

Working directory: ${PROJECT}

The API key is already configured in .env. Run:
python evaluation/run_eval.py

This will:
1. Run 30 agent evaluation cases (requires DeepSeek API)
2. Run 15 RAG evaluation cases
3. Save report to evaluation/eval_report.json

IMPORTANT: If the agent eval takes too long (more than 5 minutes), it might be because the API calls are slow. In that case, analyze any errors and report them.

After running, read evaluation/eval_report.json and report the full results including:
- Agent eval: TP, FP, FN, TN, precision, recall, F1, accuracy
- RAG eval: hits, total, recall rate

Report ALL numbers clearly.`, {
  label: 'run-agent-eval',
  phase: 'P0 评测运行',
})

// 3c. 分析评测结果并修复问题
await agent(`Analyze the evaluation results and fix any issues.

Read ${PROJECT}/evaluation/eval_report.json

If agent evaluation was skipped or failed:
1. Check if the API key works by running a simple test:
   python -c "import sys; sys.path.insert(0,'backend'); sys.path.insert(0,'pipeline'); from langchain_openai import ChatOpenAI; import config; llm=ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY); r=llm.invoke('hello'); print('API OK:', r.content[:50])"
2. If API works but eval fails, check the error and fix it
3. If API doesn't work, report the error message

If the evaluation ran successfully, analyze the results:
- What is the precision/recall/F1?
- Which cases were misclassified (FP/FN)?
- Suggest prompt improvements if F1 < 0.8

Working directory: ${PROJECT}`, {
  label: 'analyze-eval-results',
  phase: 'P0 评测运行',
})


// =======================================================================
// Phase 4: P1 统计面板 — 确保 /api/stats 返回真实数据
// =======================================================================

phase('P1 统计面板')

// 4a. 验证统计面板数据流
await agent(`Verify the stats data flow end-to-end.

Working directory: ${PROJECT}

1. Start the backend briefly and test the stats endpoint:
   python -c "
import sys; sys.path.insert(0,'backend'); sys.path.insert(0,'pipeline')
from store import ReviewStore
rs = ReviewStore()
stats = rs.get_stats()
import json; print(json.dumps(stats, ensure_ascii=False, indent=2))
"

2. If the review.db doesn't have any data yet, run a few test reviews through the agent to populate it:
   python -c "
import sys, asyncio
sys.path.insert(0,'backend'); sys.path.insert(0,'pipeline')
from agent import ComplianceAgent
from schemas import ReviewRequest, Industry
import config
from store import ReviewStore

async def populate():
    agent = ComplianceAgent(config)
    store = ReviewStore()
    tests = [
        ('全网最低价，买到就是赚到！', 'ecommerce'),
        ('本产品采用优质原料，口感醇厚', 'general'),
        ('100%有效，根治痘痘', 'medicine'),
        ('销量第一，全球领先', 'ecommerce'),
        ('限时秒杀，仅此一天', 'ecommerce'),
    ]
    for text, ind in tests:
        try:
            req = ReviewRequest(text=text, industry=Industry(ind))
            resp = await agent.review(req)
            store.save_review(
                resp.review_id, text, resp.status, resp.overall_risk.value,
                len(resp.violations),
                [{'text': v.text, 'category': v.category, 'severity': v.severity.value} for v in resp.violations],
                ind
            )
            print(f'Saved: {resp.review_id} ({resp.status}, {len(resp.violations)} violations)')
        except Exception as e:
            print(f'Error: {e}')
    agent.close()
    store.close()

asyncio.run(populate())
"

3. Then verify stats again:
   python -c "
import sys; sys.path.insert(0,'backend'); sys.path.insert(0,'pipeline')
from store import ReviewStore; rs = ReviewStore()
import json; print(json.dumps(rs.get_stats(), ensure_ascii=False, indent=2))
"

Report the final stats data.`, {
  label: 'verify-stats-data',
  phase: 'P1 统计面板',
})


// =======================================================================
// Phase 5: P1 文档更新 — 更新 README 和评测报告
// =======================================================================

phase('P1 文档更新')

// 5a. 更新 README
await agent(`Update the README.md with real evaluation data and better documentation.

Read ${PROJECT}/README.md first.

Then rewrite it to include:
1. Keep the current structure but improve it
2. Add a "系统架构" section showing the 3-tier architecture:
   - Layer 1: 规则引擎 (288条禁用词正则匹配, 毫秒级)
   - Layer 2: LLM 语境判断 (DeepSeek-V4-Flash, 减少误报)
   - Layer 3: RAG 知识检索 (三库融合: 法规+案例+行业规则)
3. Update the "评测结果" section with a placeholder that says:
   ```
   Agent 评测（30题）: Precision/Recall/F1 — 运行 python evaluation/run_eval.py 获取
   RAG 评测（15题）: 召回率 86.7% (13/15)
   ```
4. Add a "技术亮点" section with 4 bullet points:
   - 规则+LLM+RAG 三层架构，每个判断有法条依据
   - vmem 向量+全文融合检索，bge-small-zh-v1.5 嵌入
   - Pydantic 全链路结构化输出，LangChain Function Calling
   - 反馈记忆系统：用户确认/修改/驳回 → 持续优化
5. Keep the "面向评委的亮点" section
6. Add a "项目结构" tree diagram

Write the updated README using the Write tool.`, {
  label: 'update-readme',
  phase: 'P1 文档更新',
})

// 5b. 最终验证
await agent(`Final verification — make sure everything works together.

Working directory: ${PROJECT}

1. Check all Python imports work:
   python -c "
import sys; sys.path.insert(0,'backend'); sys.path.insert(0,'pipeline')
from agent import ComplianceAgent
from schemas import ReviewRequest, ReviewResponse, FeedbackRequest
from store import ReviewStore
from tools.banned_word import BannedWordMatcher
from tools.context_judge import ContextJudge
from tools.regulation_rag import RegulationRAG
from tools.rewrite import RewriteGenerator
from storage import VmemStore
from retrieval import ThreeLibRetriever
print('ALL IMPORTS OK')
"

2. Verify no hardcoded paths remain:
   Search for 'D:/Desktop' in all .py files under backend/ and evaluation/

3. List all files modified and confirm the changes:
   git status

Report a summary of all changes made.`, {
  label: 'final-verification',
  phase: 'P1 文档更新',
})
