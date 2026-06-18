"""FastAPI 应用 — 广告法合规审查 API"""
import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import ReviewRequest, ReviewResponse, FeedbackRequest, FeedbackResponse, StatsResponse
from agent import ComplianceAgent
from store import ReviewStore
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
review_store = None

@app.on_event("startup")
async def startup():
    global agent_instance
    global review_store
    agent_instance = ComplianceAgent(config)
    review_store = ReviewStore()

@app.on_event("shutdown")
async def shutdown():
    if agent_instance:
        agent_instance.close()

@app.post("/api/review", response_model=ReviewResponse)
async def review(request: ReviewRequest):
    try:
        response = await agent_instance.review(request)
        review_store.save_review(
            response.review_id, request.text, response.status,
            response.overall_risk.value if hasattr(response.overall_risk, 'value') else str(response.overall_risk),
            len(response.violations),
            [{"text": v.text, "category": v.category, "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity)} for v in response.violations],
            request.industry.value if hasattr(request.industry, 'value') else str(request.industry)
        )
        return response
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
    review_store.save_feedback(
        request.review_id,
        request.violation_id,
        request.action.value if hasattr(request.action, 'value') else str(request.action),
        request.replacement
    )
    return FeedbackResponse(success=True)

@app.get("/api/stats", response_model=StatsResponse)
async def stats():
    return review_store.get_stats()

@app.get("/api/health")
async def health():
    return {"status": "ok"}
