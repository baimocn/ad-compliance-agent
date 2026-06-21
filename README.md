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
│  DeepSeek 并发语境分析 + 多维度置信度        │
│  (ContextJudge — 分层 prompt，宁可漏报不可错杀)│
└────────────────┬────────────────────────────┘
                 │ 确认违规词
                 ▼
┌─────────────────────────────────────────────┐
│  Layer 3: RAG 知识检索                       │
│  vmem 三库融合检索：法规 110 条 + 处罚案例   │
│  50 条 + 行业规则 7 个行业                   │
│  向量 0.5 + 全文 0.2 + 时间 0.1 + 置信度 0.2 │
└────────────────┬────────────────────────────┘
                 │ 法规依据 + 处罚案例 + 替代建议
                 ▼
        输出审查报告（高亮 + 法条 + 案例 + 建议）
```

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **禁用词匹配** | 288 条禁用词正则引擎，毫秒级响应，覆盖极限用语/虚假宣传/对比贬低等 8 大类 |
| **LLM 语境判断** | 分层 prompt 架构（按违规类型专用 prompt），多维度置信度输出 |
| **三层知识库** | 法规条文 110 条 + 处罚案例 50 条 + 行业规则 7 个行业，vmem 融合搜索 |
| **处罚案例关联** | 从 RAG 结果中自动提取相关处罚案例（标题、罚款金额、法条依据） |
| **替代文案生成** | 70 条禁用→替代映射表 + LLM 智能改写，给出合规替代建议 |
| **反馈记忆** | 用户确认/修改/驳回 → SQLite 持久化 → 贝叶斯置信度更新 |
| **异步审查** | RequestQueue 并发控制（最大 5 并发）+ SSE 实时进度推送 |
| **性能监控** | P50/P95/P99 延迟百分位 + 吞吐量 + 错误率实时监控 |
| **用户系统** | 注册/登录/Token 鉴权/密码重置/账户注销 |
| **套餐计费** | 免费版/专业版/企业版，用量限制 + 升级 + 模拟支付 |
| **批量审查** | 上传 txt/csv 文件，逐行审查，最多 100 条/批 |

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

### RAG 检索质量评测（15 题）

| 指标 | 数值 |
|------|------|
| **检索召回率** | **86.7%** |
| 命中 / 总数 | 13 / 15 |

### 评测脚本

```bash
python evaluation/run_eval.py
python evaluation/test_e2e.py
```

---

## 技术亮点

### 1. 三层架构，不是套壳 ChatGPT

规则引擎做第一道筛选（零 LLM 成本），LLM 做语境判断（减少误报），RAG 做法规检索（给出法条依据）。每一层都有明确职责。

### 2. vmem 融合检索

四维评分的融合检索系统：
- **向量相似度 (0.5)**：bge-small-zh-v1.5 嵌入
- **全文匹配 (0.2)**：SQLite FTS5
- **时间衰减 (0.1)**：越新的知识越优先
- **置信度 (0.2)**：基于用户反馈的贝叶斯更新

### 3. Pydantic 全链路结构化输出

从 `ReviewRequest` → `BannedWordHit` → `ContextJudgment` → `Violation` → `ReviewResponse`，全程 Pydantic 数据模型校验，LLM 输出结构化 JSON。

### 4. 反馈记忆系统

用户对审查结果的确认/修改/驳回 → SQLite 持久化 → 贝叶斯置信度更新 → 下次审查更准确。不是静态工具，是越用越准的数据飞轮。

### 5. LLM 兼容层（CompatibleLLM）

自研 LLM 包装器，兼容推理模型（如 mimo 等），解决 `reasoning_content` 与 `content` 的差异问题，统一 `ainvoke` 接口。Token 用量全链路追踪。

### 6. 分层语境判断（ContextJudge v2）

按违规类型（极限用语/虚假宣传/对比贬低/行业禁区）使用专用 prompt，多维度置信度输出（overall / violation_type / severity / context_relevance），结构化推理（evidence + mitigating_factors）。

### 7. 异步审查 + 并发控制

- `RequestQueue`：Semaphore 并发控制（最大 5 并发），队列最大 100 请求
- `PerformanceMonitor`：P50/P95/P99 延迟百分位 + 吞吐量 + 错误率
- SSE 实时进度推送：客户端通过 `EventSource` 接收审查进度

---

## 面向评委的亮点

1. **不是套壳 ChatGPT**：规则引擎 + LLM + RAG 三层架构，每个判断有法条依据
2. **有评测数据**：30 题 Agent 评测（精确率 100% / 召回率 76.9% / F1 87%）+ 15 题 RAG 评测（召回率 86.7%）
3. **零误报**：Agent 标记为违规的内容 100% 确实违规（FP=0）
4. **评委 5 秒就懂**："一次罚款 20 万，10 秒帮你查出来"
5. **快 100 倍**：30 题审查 36 秒完成，人工预估 60 分钟
6. **生产级特性**：异步队列、并发控制、性能监控、用户鉴权、套餐计费

---

## 技术栈

| 层 | 选择 |
|---|------|
| Agent 框架 | Function Calling + 自研 CompatibleLLM 兼容层 |
| LLM | DeepSeek-V4-Flash（兼容推理模型 mimo 等） |
| 知识库 | vmem (SQLite + FTS5 + numpy + bge-small-zh-v1.5) |
| 后端 | FastAPI + 异步队列 + 并发控制 + SSE |
| 前端 | Next.js + shadcn/ui + Tailwind CSS |
| 数据模型 | Pydantic v2 |
| 用户认证 | bcrypt + Token 鉴权 |
| 存储 | SQLite (review.db + vmem.db) |

---

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- DeepSeek API Key

### 安装依赖

```bash
pip install -r requirements-backend.txt
pip install -r requirements-data.txt
cd frontend && npm install
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 启动

```bash
# 方式一：Windows 一键启动
start_all.bat

# 方式二：分别启动
python -m uvicorn backend.main:app --reload --port 8000   # 后端
cd frontend && npm run dev                                  # 前端
```

### 构建知识库（首次）

```bash
python pipeline/run_pipeline.py
```

---

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 25 个 API 端点（用户+审查+计费+异步+监控）
│   ├── agent.py                # ComplianceAgent 主编排
│   ├── schemas.py              # Pydantic 数据模型（含异步/性能/计费模型）
│   ├── config.py               # 配置加载（.env）
│   ├── store.py                # 用户/审查/计费/反馈存储 (SQLite)
│   ├── llm_compat.py           # CompatibleLLM 兼容层
│   └── tools/                  # Agent 工具集
│       ├── banned_word.py      # 工具1: 禁用词规则匹配
│       ├── context_judge.py    # 工具2: LLM 语境判断 v2（分层 prompt）
│       ├── regulation_rag.py   # 工具3: 法规 RAG 检索
│       └── rewrite.py          # 工具4: 替代文案生成
│
├── pipeline/                   # 数据管线 + 知识库构建
│   ├── parsers.py / retrieval.py / storage.py / run_pipeline.py
│   └── data/                   # 知识库数据 (vmem.db, review.db, 禁用词/)
│
├── frontend/                   # Next.js 前端
│   └── src/
│       ├── app/                # 页面 (首页/审查/历史/统计/定价/设置/登录/注册)
│       ├── components/         # 组件 (ui/ 导航栏/批量上传)
│       ├── lib/                # API 客户端/认证/导出
│       └── hooks/              # 自定义 hooks
│
├── vmem/                       # 记忆向量存储系统
├── evaluation/                 # 评测集 + 评测脚本
├── 数据集/                      # 原始法规/案例/禁用词数据
├── .env.example / requirements-backend.txt / requirements-data.txt
└── start_all.bat / start_backend.bat / start_frontend.bat
```

---

## API 接口（25 个端点）

### 认证（6 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auth/register` | 用户注册 |
| `POST` | `/api/auth/login` | 用户登录 |
| `GET` | `/api/me` | 当前用户信息 |
| `POST` | `/api/auth/forgot-password` | 找回密码 |
| `POST` | `/api/auth/reset-password` | 重置密码 |
| `DELETE` | `/api/account` | 注销账户 |

### 审查（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/review` | 同步审查（支持可选鉴权） |
| `POST` | `/api/review/async` | 异步审查 |
| `GET` | `/api/review/{request_id}` | 查询异步审查状态 |
| `GET` | `/api/review/{request_id}/stream` | SSE 实时进度 |
| `POST` | `/api/batch-review` | 批量审查（txt/csv） |

### 反馈 & 统计（6 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/feedback` | 提交反馈（需登录） |
| `GET` | `/api/feedback/stats` | 反馈统计 |
| `GET` | `/api/stats` | 审查统计 |
| `GET` | `/api/reviews` | 审查历史（分页） |
| `GET` | `/api/reviews/{review_id}` | 单条详情 |
| `GET` | `/api/my-reviews` | 我的审查历史 |

### 计费（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/plans` | 套餐列表 |
| `GET` | `/api/my-plan` | 当前套餐 |
| `GET` | `/api/usage` | 用量统计 |
| `POST` | `/api/upgrade` | 升级套餐 |
| `POST` | `/api/simulate-payment` | 模拟支付 |

### 系统（3 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/metrics` | 性能指标 |
| `GET` | `/api/queue/status` | 队列状态 |
| `POST` | `/api/test-connection` | 测试 LLM 连接 |

### 审查请求示例

```json
POST /api/review
{
  "text": "全网最低价，买到就是赚到！",
  "industry": "ecommerce",
  "model": "deepseek-chat"
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
      "confidence": 0.95,
      "law_article": "《广告法》第九条第三项",
      "law_content": "第五十七条 有下列行为之一的...",
      "explanation": "使用绝对化用语「最低」构成违规",
      "suggestions": [{"original": "最低", "replacement": "优惠", "reason": "从合规映射表匹配"}],
      "related_cases": [{"title": "某电商平台最低价处罚案", "penalty": "罚款 20 万元"}]
    }
  ],
  "summary": "检测到 2 处违规，最高风险等级：high",
  "processing_time_ms": 1200,
  "token_usage": {"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
  "pipeline_steps": [
    {"step": 1, "name": "禁用词匹配", "status": "completed", "detail": "命中 2 个疑似禁用词", "icon": "🔍"},
    {"step": 2, "name": "LLM 语境判断", "status": "completed", "detail": "确认 2 个违规，排除 0 个误报", "icon": "🧠"},
    {"step": 3, "name": "RAG 法规检索", "status": "completed", "detail": "检索到 6 条法规依据", "icon": "📚"},
    {"step": 4, "name": "替代建议生成", "status": "completed", "detail": "生成 2 条合规替代建议", "icon": "✏️"}
  ]
}
```

---

## 更新日志

### v2.0 — 2026-06-21

合并两个开发分支的优势功能：

**新增**
- `llm_compat.py`：CompatibleLLM 兼容推理模型，token 用量全链路追踪
- ContextJudge v2：分层 prompt + 多维度置信度 + 结构化推理
- 异步审查管线：RequestQueue + PerformanceMonitor + SSE 推送
- 用户系统：注册/登录/鉴权/密码重置/注销
- 套餐计费：免费版/专业版/企业版 + 用量限制
- 批量审查：txt/csv 文件上传，最多 100 条/批
- 反馈统计 + 异步置信度学习闭环
- 前端：登录/注册/定价/设置/批量上传页面
- 处罚案例自动关联（从 RAG 结果提取）

**修复**
- SSR hydration 不匹配（SettingsPanel localStorage 读取时机）
- 法条依据字段映射（camelCase 转换兼容）

---

## License

本项目为 Agent Hackathon 参赛作品，仅供学习和评审使用。
