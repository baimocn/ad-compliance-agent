"""FastAPI 应用 — 广告法合规审查 API"""
import sys
sys.path.insert(0, 'D:/Desktop/黑客松/backend')
sys.path.insert(0, 'D:/Desktop/黑客松/pipeline')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import ReviewRequest, ReviewResponse, FeedbackRequest, FeedbackResponse, StatsResponse
from agent import ComplianceAgent
import config

app = FastAPI(title="广告法合规审查 Agent", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent 实例
agent_instance = None

@app.on_event("startup")
async def startup():
    global agent_instance
    agent_instance = ComplianceAgent(config)

@app.on_event("shutdown")
async def shutdown():
    if agent_instance:
        agent_instance.close()

@app.post("/api/review", response_model=ReviewResponse)
async def review(request: ReviewRequest):
    try:
        return await agent_instance.review(request)
    except Exception as e:
        error_msg = str(e)
        # 返回一个带错误信息的安全降级响应
        return ReviewResponse(
            review_id=f"ERR-{int(__import__('time').time())}",
            status="error",
            overall_risk="pass",
            violations=[],
            highlighted_text=request.text,
            summary=f"审查出错: {error_msg[:200]}。请检查 API Key 是否正确。",
            reviewed_at=__import__('time').strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest):
    # 反馈存储到 vmem（Phase 1 的 feedback.py 会在后续集成）
    return FeedbackResponse(success=True)

@app.get("/api/stats", response_model=StatsResponse)
async def stats():
    return StatsResponse()

@app.get("/api/health")
async def health():
    return {"status": "ok"}
