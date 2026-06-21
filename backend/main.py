"""FastAPI 应用 — 广告法合规审查 API（含用户账号系统）"""
import sys
import csv
import io
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

import re
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from schemas import ReviewRequest, ReviewResponse, FeedbackRequest, FeedbackResponse, StatsResponse, UpgradeRequest
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
    global agent_instance, review_store
    agent_instance = ComplianceAgent(config)
    review_store = ReviewStore()

@app.on_event("shutdown")
async def shutdown():
    if agent_instance:
        agent_instance.close()

# ---------- 认证依赖 ----------

def get_current_user(authorization: str = Header(None)):
    """从 Authorization header 解析 token，返回用户信息或 None"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    return review_store.get_user_by_token(token)

# ---------- 用户认证 API ----------

@app.post("/api/auth/register")
async def register(body: dict):
    """注册：{username, password}"""
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码长度至少8位")
    if not re.search(r'[a-zA-Z]', password) or not re.search(r'\d', password):
        raise HTTPException(status_code=400, detail="密码必须包含字母和数字")
    result = review_store.create_user(username, password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    # 自动登录，返回 token
    token = review_store.create_token(result["user_id"])
    return {"success": True, "token": token, "username": username, "user_id": result["user_id"]}

@app.post("/api/auth/login")
async def login(body: dict):
    """登录：{username, password}"""
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    result = review_store.verify_user(username, password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    token = review_store.create_token(result["user_id"])
    return {"success": True, "token": token, "username": result["username"], "user_id": result["user_id"]}

@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"success": True, "user_id": user["user_id"], "username": user["username"]}

@app.get("/api/my-reviews")
async def get_my_reviews(user: dict = Depends(get_current_user), limit: int = 50,
                         risk: str = None, query: str = None,
                         date_from: str = None, date_to: str = None):
    """获取我的审查历史，支持筛选"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    reviews = review_store.get_user_reviews(user["user_id"], limit, risk, query, date_from, date_to)
    return {"success": True, "reviews": reviews}

@app.post("/api/auth/forgot-password")
async def forgot_password(body: dict):
    username = (body.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="请输入用户名")
    result = review_store.create_password_reset(username)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "reset_token": result["reset_token"],
            "message": "重置令牌已生成（hackathon 阶段直接返回，正式上线应通过邮件发送）"}

@app.post("/api/auth/reset-password")
async def reset_password(body: dict):
    username = (body.get("username") or "").strip()
    reset_token = (body.get("reset_token") or "").strip()
    new_password = body.get("new_password") or ""
    if not username or not reset_token or not new_password:
        raise HTTPException(status_code=400, detail="参数不完整")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="密码长度至少8位")
    if not re.search(r'[a-zA-Z]', new_password) or not re.search(r'\d', new_password):
        raise HTTPException(status_code=400, detail="密码必须包含字母和数字")
    result = review_store.reset_password(username, reset_token, new_password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "message": "密码已重置"}

@app.delete("/api/account")
async def delete_account(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    review_store.delete_account(user["user_id"])
    return {"success": True, "message": "账户及所有数据已删除"}

# ---------- 计费 API ----------

@app.get("/api/plans")
async def get_plans():
    return {"success": True, "plans": review_store.get_plans()}

@app.get("/api/my-plan")
async def get_my_plan(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"success": True, "plan": review_store.get_user_plan(user["user_id"])}

@app.get("/api/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"success": True, **review_store.get_usage_stats(user["user_id"])}

@app.post("/api/upgrade")
async def upgrade(body: UpgradeRequest, user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    result = review_store.upgrade_plan(user["user_id"], body.plan_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "plan": result["plan"]}

@app.post("/api/simulate-payment")
async def simulate_payment(body: UpgradeRequest, user: dict = Depends(get_current_user)):
    """模拟支付流程 —— hackathon 阶段，点击即成功"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    result = review_store.upgrade_plan(user["user_id"], body.plan_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "message": f"已升级至 {result['plan']['name']}", "plan": result["plan"]}

@app.post("/api/test-connection")
async def test_connection(body: dict = None):
    """测试 LLM API 连接"""
    api_key = (body.get("api_key") or "").strip() if body else ""
    base_url = (body.get("base_url") or "").strip() if body else ""
    model = (body.get("model") or "").strip() if body else ""
    if not api_key:
        raise HTTPException(status_code=400, detail="请输入 API Key")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url or config.LLM_BASE_URL)
        chat_model = model or config.LLM_MODEL
        resp = client.chat.completions.create(
            model=chat_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
        )
        choice = resp.choices[0].message if resp.choices else None
        content = (choice.content or "") if choice else ""
        reasoning = getattr(choice, "reasoning_content", "") if choice else ""
        if resp and (content.strip() or reasoning.strip()):
            return {"success": True, "message": "连接成功"}
        raise HTTPException(status_code=400, detail="连接失败：模型未返回内容")
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)[:200]
        if "401" in error_str or "unauthorized" in error_str.lower() or "invalid" in error_str.lower():
            raise HTTPException(status_code=400, detail="认证失败：API Key 无效")
        raise HTTPException(status_code=400, detail=f"连接失败：{error_str[:100]}")

# ---------- 主功能 API ----------

@app.post("/api/review", response_model=ReviewResponse)
async def review(request: ReviewRequest, user: dict = Depends(get_current_user)):
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="服务尚未初始化，请稍后重试")
    if user:
        review_store.ensure_user_plan(user["user_id"])
        limit_check = review_store.check_usage_limit(user["user_id"])
        if not limit_check["allowed"]:
            raise HTTPException(status_code=402, detail=limit_check["reason"])
    try:
        response = await agent_instance.review(request)
        review_store.save_review(
            response.review_id, request.text, response.status,
            response.overall_risk.value if hasattr(response.overall_risk, 'value') else str(response.overall_risk),
            len(response.violations),
            [{"text": v.text, "category": v.category, "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity)} for v in response.violations],
            request.industry.value if hasattr(request.industry, 'value') else str(request.industry),
            user_id=user["user_id"] if user else None,
        )
        if user:
            tokens = response.token_usage.get("total_tokens", 0) if response.token_usage else 0
            review_store.log_usage(user["user_id"], review_count=1, tokens=tokens)
        return response
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        import time
        raise HTTPException(
            status_code=500,
            detail=f"审查出错: {error_msg[:200]}。请检查 API Key 是否正确。",
        )

@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest, user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    review_store.save_feedback(
        request.review_id,
        request.violation_id,
        request.action.value if hasattr(request.action, 'value') else str(request.action),
        request.replacement
    )
    return FeedbackResponse(success=True)

@app.get("/api/stats", response_model=StatsResponse)
async def stats(user: dict = Depends(get_current_user)):
    user_id = user["user_id"] if user else None
    return review_store.get_stats(user_id)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# ---------- 批量审查 API ----------

@app.post("/api/batch-review")
async def batch_review(
    file: UploadFile = File(...),
    industry: str = Form("general"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """批量审查：上传 txt/csv 文件，逐行审查"""
    content = await file.read()
    texts = []
    filename = file.filename or "upload.txt"

    try:
        if filename.endswith(".csv"):
            # 解析 CSV：取第一列非空行
            text_io = io.StringIO(content.decode("utf-8", errors="replace"))
            reader = csv.reader(text_io)
            for row in reader:
                if row and row[0].strip():
                    texts.append(row[0].strip())
        else:
            # 默认按 txt 处理：每行一条文案
            text_io = content.decode("utf-8", errors="replace")
            for line in text_io.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    texts.append(line)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{str(e)}")

    if not texts:
        raise HTTPException(status_code=400, detail="文件中未找到可审查的文案")
    if len(texts) > 100:
        raise HTTPException(status_code=400, detail=f"最多支持 100 条文案，当前 {len(texts)} 条")

    if user:
        review_store.ensure_user_plan(user["user_id"])
        limit_check = review_store.check_usage_limit(user["user_id"])
        if not limit_check["allowed"]:
            raise HTTPException(status_code=402, detail=limit_check["reason"])

    from schemas import Industry
    try:
        ind = Industry(industry)
    except ValueError:
        ind = Industry.GENERAL

    results = []
    for i, text in enumerate(texts):
        try:
            req = ReviewRequest(text=text, industry=ind, api_key=api_key or None, base_url=base_url or None, model=model or None)
            resp = await agent_instance.review(req)
            results.append({
                "index": i + 1,
                "text": text[:100],
                "status": resp.status,
                "overall_risk": resp.overall_risk.value if hasattr(resp.overall_risk, 'value') else str(resp.overall_risk),
                "violation_count": len(resp.violations),
                "violations": [{"text": v.text, "category": v.category, "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity), "suggestion": v.suggestions[0].replacement if v.suggestions else ""} for v in resp.violations],
                "review_id": resp.review_id,
            })
            # 保存审查记录
            review_store.save_review(
                resp.review_id, text, resp.status,
                resp.overall_risk.value if hasattr(resp.overall_risk, 'value') else str(resp.overall_risk),
                len(resp.violations),
                [{"text": v.text, "category": v.category, "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity)} for v in resp.violations],
                industry,
                user_id=user["user_id"] if user else None,
            )
        except Exception as e:
            results.append({
                "index": i + 1,
                "text": text[:100],
                "status": "error",
                "overall_risk": "error",
                "violation_count": 0,
                "violations": [],
                "error": str(e)[:200],
            })

    # 汇总
    total = len(results)
    risk_counts = {"high": 0, "medium": 0, "low": 0, "pass": 0, "error": 0}
    for r in results:
        k = r["overall_risk"]
        if k in risk_counts:
            risk_counts[k] += 1
        else:
            risk_counts["error"] += 1

    if user:
        success_count = sum(1 for r in results if r["status"] != "error")
        review_store.log_usage(user["user_id"], review_count=success_count, batch_count=1)

    return {
        "success": True,
        "total": total,
        "results": results,
        "summary": {
            "high": risk_counts["high"],
            "medium": risk_counts["medium"],
            "low": risk_counts["low"],
            "pass": risk_counts["pass"],
            "error": risk_counts["error"],
        }
    }
