# 广告法合规审查 Agent

> Agent Hackathon 大赛参赛作品 | AtomGit AI × Ascend 昇腾

## 一句话定位

帮电商运营和自媒体创作者自动审查广告文案是否违反《广告法》，标注违规点并给出合规替代建议。

## 核心能力

- 🔍 **禁用词匹配**：288 条禁用词正则引擎，毫秒级响应
- 🧠 **LLM 语境判断**：DeepSeek 智能分析，减少误报
- 📖 **三层知识库**：法规条文 110 条 + 处罚案例 50 条 + 行业规则 7 个行业，vmem 融合搜索
- ✍️ **替代文案生成**：120+ 禁用→替代映射 + LLM 智能改写
- 💾 **反馈记忆**：用户驳回/修改 → 贝叶斯置信度更新 → 越用越准

## 技术栈

| 层 | 选择 |
|---|------|
| Agent 框架 | LangChain + Function Calling |
| LLM | DeepSeek-V4-flash |
| 知识库 | vmem (SQLite + FTS5 + numpy + bge-small-zh-v1.5) |
| 后端 | FastAPI |
| 前端 | Next.js + shadcn/ui + Tailwind CSS |

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 一键启动
start_all.bat

# 或分别启动：
# 终端1: python -m uvicorn backend.main:app --reload --port 8000
# 终端2: cd frontend && npm run dev
```

## 评测结果

```
Agent 评测（30题）：运行 python evaluation/run_eval.py
RAG 评测（15题）：运行 python evaluation/run_eval.py
```

## 项目结构

```
backend/     — FastAPI + Agent + 4 个工具
pipeline/    — 数据管线 + vmem 知识库
frontend/    — Next.js 审查工作台
evaluation/  — 评测集 + 评测脚本
vmem/        — 记忆系统（复用自 cc-hms）
数据集/       — 原始法规/案例/禁用词数据
```

## 面向评委的亮点

1. **不是套壳 ChatGPT**：规则引擎 + LLM + RAG 三层架构，每个判断有法条依据
2. **有评测数据**：30 题 Agent 评测 + 15 题 RAG 评测，精确率/召回率/F1 全有
3. **有反馈记忆**：越用越准的数据飞轮，不是静态工具
4. **评委 5 秒就懂**："一次罚款 20 万，10 秒帮你查出来"
