# 广告法合规审查 Agent

> Agent Hackathon 大赛参赛作品 | AtomGit AI × Ascend 昇腾

## 一句话定位

帮电商运营和自媒体创作者自动审查广告文案是否违反《广告法》，标注违规点并给出合规替代建议。

---

## 系统架构

三层架构，不是套壳 ChatGPT，每个判断都有法条依据：

```
用户输入文案
    │
    ▼
┌─────────────────────────────────────────────┐
│  Layer 1: 规则引擎                           │
│  288 条禁用词正则匹配，毫秒级响应            │
│  (BannedWordMatcher — 纯确定性，零 LLM 成本) │
└────────────────┬────────────────────────────┘
                 │ 命中词列表
                 ▼
┌─────────────────────────────────────────────┐
│  Layer 2: LLM 语境判断                       │
│  DeepSeek-V4-Flash 并发语境分析              │
│  (ContextJudge — 减少误报，宁可漏报不可错杀) │
└────────────────┬────────────────────────────┘
                 │ 确认违规词
                 ▼
┌─────────────────────────────────────────────┐
│  Layer 3: RAG 知识检索                       │
│  vmem 三库融合检索：法规 110 条 + 处罚案例   │
│  50 条 + 行业规则 7 个行业                   │
│  向量 0.5 + 全文 0.2 + 时间 0.1 + 置信度 0.2 │
└────────────────┬────────────────────────────┘
                 │ 法规依据 + 替代建议
                 ▼
        输出审查报告（高亮 + 法条 + 建议）
```

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **禁用词匹配** | 288 条禁用词正则引擎，毫秒级响应，覆盖极限用语/虚假宣传/对比贬低等 8 大类 |
| **LLM 语境判断** | DeepSeek 智能分析，区分营销违规 vs 客观参数，减少误报 |
| **三层知识库** | 法规条文 110 条 + 处罚案例 50 条 + 行业规则 7 个行业，vmem 融合搜索 |
| **替代文案生成** | 70 条禁用→替代映射表 + LLM 智能改写，给出合规替代建议 |
| **反馈记忆** | 用户确认/修改/驳回 → SQLite 持久化，越用越准的数据飞轮 |

---

## 评测结果

### Agent 端到端评测（30 题）

覆盖 10 类违规场景 + 10 类正常文案 + 10 类边界案例：

| 指标 | 数值 |
|------|------|
| **准确率 (Accuracy)** | **90.0%** |
| **精确率 (Precision)** | **100.0%** |
| **召回率 (Recall)** | **76.9%** |
| **F1 分数** | **87.0%** |
| TP / FP / FN / TN | 10 / 0 / 3 / 17 |
| **总耗时** | **36 秒（1.2 秒/题）** |
| **人工对比** | 人工预估 60 分钟，Agent 快 100 倍 |

> **零误报**（FP=0）：Agent 标记为违规的内容，100% 确实违规。
> 评测集包含极限用语、虚假宣传、对比贬低、行业禁区等违规样本，以及正常产品描述、事实参数、边界案例等非违规样本。

### RAG 检索质量评测（15 题）

覆盖法规查询、处罚案例检索、行业规则检索三类场景：

| 指标 | 数值 |
|------|------|
| **检索召回率** | **86.7%** |
| 命中 / 总数 | 13 / 15 |

> 15 题覆盖：全网最低价、国家级用语、食品功效宣传、未成年人代言、虚假广告认定、化妆品违规、电商平台处罚、保健食品处罚、直播间虚假宣传、教育培训处罚、抖音审核规则、小红书种草标注、化妆品对比效果图、金融理财合规、房地产广告规范。

### 评测脚本

```bash
# 运行完整评测（需配置 DEEPSEEK_API_KEY）
python evaluation/run_eval.py

# 运行端到端测试
python evaluation/test_e2e.py
```

---

## 技术亮点

### 1. 三层架构，不是套壳 ChatGPT

规则引擎做第一道筛选（零 LLM 成本），LLM 做语境判断（减少误报），RAG 做法规检索（给出法条依据）。每一层都有明确职责，不是简单把文案扔给大模型。

### 2. vmem 融合检索

四维评分的融合检索系统：
- **向量相似度 (0.5)**：bge-small-zh-v1.5 嵌入
- **全文匹配 (0.2)**：SQLite FTS5
- **时间衰减 (0.1)**：越新的知识越优先
- **置信度 (0.2)**：基于用户反馈的贝叶斯更新

### 3. Pydantic 全链路结构化输出

从 `ReviewRequest` → `BannedWordHit` → `ContextJudgment` → `Violation` → `ReviewResponse`，全程 Pydantic 数据模型校验，LangChain Function Calling 保证 LLM 输出结构化 JSON。

### 4. 反馈记忆系统

用户对审查结果的确认/修改/驳回 → SQLite 持久化 → 贝叶斯置信度更新 → 下次审查更准确。不是静态工具，是越用越准的数据飞轮。

---

## 面向评委的亮点

1. **不是套壳 ChatGPT**：规则引擎 + LLM + RAG 三层架构，每个判断有法条依据
2. **有评测数据**：30 题 Agent 评测（精确率 100% / 召回率 76.9% / F1 87%）+ 15 题 RAG 评测（召回率 86.7%）
3. **零误报**：Agent 标记为违规的内容 100% 确实违规（FP=0）
4. **评委 5 秒就懂**："一次罚款 20 万，10 秒帮你查出来"
5. **快 100 倍**：30 题审查 36 秒完成，人工预估 60 分钟

---

## 技术栈

| 层 | 选择 |
|---|------|
| Agent 框架 | LangChain + Function Calling |
| LLM | DeepSeek-V4-Flash |
| 知识库 | vmem (SQLite + FTS5 + numpy + bge-small-zh-v1.5) |
| 后端 | FastAPI |
| 前端 | Next.js + shadcn/ui + Tailwind CSS |
| 数据模型 | Pydantic v2 |
| 反馈存储 | SQLite (review.db) |

---

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- DeepSeek API Key

### 安装依赖

```bash
# 后端依赖
pip install -r requirements-backend.txt

# 数据管线依赖（首次需要，用于构建知识库）
pip install -r requirements-data.txt

# 前端依赖
cd frontend && npm install
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 启动

```bash
# 方式一：Windows 一键启动
start_all.bat

# 方式二：分别启动
# 终端 1 — 后端 (http://localhost:8000)
python -m uvicorn backend.main:app --reload --port 8000

# 终端 2 — 前端 (http://localhost:3000)
cd frontend && npm run dev
```

### 构建知识库（首次）

```bash
# 解析法规/案例/禁用词数据 → vmem 数据库
python pipeline/run_pipeline.py
```

---

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── main.py                 # FastAPI 应用入口
│   ├── agent.py                # ComplianceAgent 主编排
│   ├── schemas.py              # Pydantic 数据模型
│   ├── config.py               # 配置加载（.env）
│   ├── store.py                # 审查记录 + 反馈存储 (SQLite)
│   └── tools/                  # Agent 工具集
│       ├── banned_word.py      # 工具1: 禁用词规则匹配
│       ├── context_judge.py    # 工具2: LLM 语境判断
│       ├── regulation_rag.py   # 工具3: 法规 RAG 检索
│       └── rewrite.py          # 工具4: 替代文案生成
│
├── pipeline/                   # 数据管线 + 知识库构建
│   ├── parsers.py              # 法规/案例/禁用词解析器
│   ├── retrieval.py            # ThreeLibRetriever 三库并行检索
│   ├── storage.py              # VmemStore 封装
│   ├── run_pipeline.py         # 一键构建知识库
│   └── data/                   # 知识库数据
│       ├── vmem.db             # vmem 向量数据库
│       ├── review.db           # 审查记录数据库
│       ├── 禁用词/             # 原始禁用词 JSON
│       └── parsed/             # 解析后的结构化数据
│           ├── ad_law.json     # 广告法条文 (110 条)
│           ├── penalty_cases.json  # 处罚案例 (50 条)
│           ├── industry_rules.json # 行业规则 (7 个行业)
│           ├── banned_words.json   # 禁用词库 (288 条)
│           └── replacement.json    # 替代映射 (70 条)
│
├── frontend/                   # Next.js 前端
│   ├── src/app/                # 页面
│   │   ├── page.tsx            # 首页
│   │   ├── review/page.tsx     # 审查工作台
│   │   └── stats/page.tsx      # 数据统计
│   ├── src/components/ui/      # shadcn/ui 组件
│   ├── src/lib/api.ts          # API 客户端
│   └── src/types/review.ts     # TypeScript 类型定义
│
├── vmem/                       # 记忆向量存储系统
│   ├── store.py                # MemoryVectorStore 核心实现
│   ├── backfill.py             # 数据回填工具
│   └── migrations.py           # 数据库迁移
│
├── evaluation/                 # 评测集 + 评测脚本
│   ├── agent_eval_cases.json   # Agent 评测集 (30 题)
│   ├── rag_eval_cases.json     # RAG 评测集 (15 题)
│   ├── eval_report.json        # 评测报告
│   ├── run_eval.py             # 评测脚本
│   └── test_e2e.py             # 端到端测试
│
├── 数据集/                      # 原始法规/案例/禁用词数据
│
├── .env.example                # 环境变量模板
├── requirements-backend.txt    # 后端 Python 依赖
├── requirements-data.txt       # 数据管线 Python 依赖
├── start_all.bat               # Windows 一键启动
├── start_backend.bat           # 后端启动脚本
└── start_frontend.bat          # 前端启动脚本
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/review` | 提交广告文案进行合规审查 |
| `POST` | `/api/feedback` | 提交审查结果反馈（确认/修改/驳回） |
| `GET` | `/api/stats` | 获取审查统计数据 |
| `GET` | `/api/health` | 健康检查 |

### 审查请求示例

```json
POST /api/review
{
  "text": "全网最低价，买到就是赚到！",
  "industry": "ecommerce"
}
```

### 审查响应示例

```json
{
  "review_id": "CR-1718750400-a1b2",
  "status": "violation_found",
  "overall_risk": "high",
  "violations": [
    {
      "text": "最低",
      "category": "极限用语",
      "severity": "high",
      "law_article": "《广告法》第九条第三项",
      "explanation": "使用绝对化用语「最低」构成违规",
      "suggestions": [{"original": "最低", "replacement": "优惠", "reason": "从合规映射表匹配"}]
    }
  ],
  "summary": "检测到 2 处违规，最高风险等级：high"
}
```

---

## License

本项目为 Agent Hackathon 参赛作品，仅供学习和评审使用。
