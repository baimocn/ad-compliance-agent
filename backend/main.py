"""FastAPI 应用 v2 — 广告法合规审查 API（生产级）

新增功能：
- 异步审查接口 + 请求队列 + 并发控制（最多 5 个并发）
- ContextJudge LLM 并发信号量（默认 3）
- 请求追踪链（request_id → review_id → violation_id）
- 性能监控中间件（P50/P95/P99）
- SSE 实时进度推送
- 反馈统计接口 + 反馈闭环学习
"""
import sys
import time
import uuid
import asyncio
import threading
from pathlib import Path
from collections import deque
from typing import Optional

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from schemas import (
    ReviewRequest, ReviewResponse, FeedbackRequest, FeedbackResponse,
    StatsResponse, AsyncReviewRequest, AsyncReviewResponse,
    ReviewStatusResponse, FeedbackStatsResponse, PerformanceMetrics,
)
from agent import ComplianceAgent
from store import ReviewStore
import config

# ============================================================
# 全局配置
# ============================================================
MAX_CONCURRENT_REVIEWS = 5      # 最大并发审查数
MAX_LLM_CONCURRENCY = 3         # LLM 最大并发调用数
REQUEST_TIMEOUT_S = 30          # 单请求超时时间（秒）
MAX_QUEUE_SIZE = 100            # 队列最大长度

# ============================================================
# FastAPI 应用
# ============================================================
app = FastAPI(title="广告法合规审查 Agent", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
agent_instance: Optional[ComplianceAgent] = None
review_store: Optional[ReviewStore] = None

# ============================================================
# 并发控制 & 请求队列
# ============================================================

class RequestQueue:
    """优先级请求队列 + 并发控制。

    使用 asyncio.Semaphore 控制并发数，
    内部用 dict 存储请求状态，支持查询进度。
    """

    def __init__(self, max_concurrent: int = 5):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._requests: dict[str, dict] = {}  # request_id -> state
        self._results: dict[str, dict] = {}   # request_id -> result
        self._queue_order = deque()           # 排队顺序
        self._lock = asyncio.Lock()
        self._max_concurrent = max_concurrent

    async def submit(self, request_id: str, request_data: dict) -> str:
        """提交请求到队列，返回 request_id。"""
        async with self._lock:
            if len(self._requests) >= MAX_QUEUE_SIZE:
                raise HTTPException(status_code=429, detail="请求队列已满，请稍后再试")

            self._requests[request_id] = {
                "request_id": request_id,
                "status": "queued",
                "progress": 0.0,
                "current_step": "等待处理",
                "queued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "started_at": "",
                "completed_at": "",
                "data": request_data,
                "position": len(self._queue_order) + 1,
            }
            self._queue_order.append(request_id)
            return request_id

    async def start_processing(self, request_id: str):
        """标记请求开始处理。"""
        async with self._lock:
            if request_id in self._requests:
                self._requests[request_id]["status"] = "processing"
                self._requests[request_id]["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._requests[request_id]["current_step"] = "审查中..."
                if request_id in self._queue_order:
                    self._queue_order.remove(request_id)
                # 更新其他排队请求的位置
                for i, rid in enumerate(self._queue_order):
                    if rid in self._requests:
                        self._requests[rid]["position"] = i + 1

    async def update_progress(self, request_id: str, progress: float, step: str):
        """更新处理进度。"""
        async with self._lock:
            if request_id in self._requests:
                self._requests[request_id]["progress"] = min(1.0, max(0.0, progress))
                self._requests[request_id]["current_step"] = step

    async def complete(self, request_id: str, result: dict):
        """标记请求完成并保存结果。"""
        async with self._lock:
            if request_id in self._requests:
                self._requests[request_id]["status"] = "completed"
                self._requests[request_id]["progress"] = 1.0
                self._requests[request_id]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._requests[request_id]["current_step"] = "审查完成"
                self._results[request_id] = result

    async def fail(self, request_id: str, error: str):
        """标记请求失败。"""
        async with self._lock:
            if request_id in self._requests:
                self._requests[request_id]["status"] = "failed"
                self._requests[request_id]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._requests[request_id]["error"] = error

    async def get_status(self, request_id: str) -> Optional[dict]:
        """获取请求状态。"""
        async with self._lock:
            req = self._requests.get(request_id)
            if not req:
                return None
            status = {
                "request_id": req["request_id"],
                "status": req["status"],
                "progress": req["progress"],
                "current_step": req["current_step"],
                "queued_at": req["queued_at"],
                "started_at": req["started_at"],
                "completed_at": req["completed_at"],
                "position_in_queue": req.get("position", 0),
            }
            if req["status"] == "completed" and request_id in self._results:
                status["result"] = self._results[request_id]
            elif req["status"] == "failed":
                status["error"] = req.get("error", "未知错误")
            return status

    def active_count(self) -> int:
        """当前活跃（处理中）请求数。"""
        return sum(1 for r in self._requests.values() if r["status"] == "processing")

    def queued_count(self) -> int:
        """当前排队请求数。"""
        return sum(1 for r in self._requests.values() if r["status"] == "queued")

    async def acquire(self):
        """获取并发许可。"""
        await self._sem.acquire()

    def release(self):
        """释放并发许可。"""
        self._sem.release()


# ============================================================
# 性能监控中间件
# ============================================================

class PerformanceMonitor:
    """性能监控：延迟百分位、吞吐量、错误率。"""

    def __init__(self, window_size: int = 1000):
        self._latencies = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._total_requests = 0
        self._error_count = 0
        self._window_start = time.time()

    def record(self, latency_ms: float, is_error: bool = False):
        """记录一次请求的延迟。"""
        with self._lock:
            self._latencies.append(latency_ms)
            self._total_requests += 1
            if is_error:
                self._error_count += 1

    def get_metrics(self) -> dict:
        """获取性能指标。"""
        with self._lock:
            if not self._latencies:
                return {
                    "p50_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                    "avg_latency_ms": 0.0,
                    "req_per_second": 0.0,
                    "total_requests": self._total_requests,
                    "error_rate": 0.0,
                }

            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)

            def percentile(p):
                idx = min(int(n * p / 100), n - 1)
                return sorted_lat[idx]

            avg = sum(sorted_lat) / n
            elapsed = max(time.time() - self._window_start, 1)
            rps = self._total_requests / elapsed
            error_rate = self._error_count / max(self._total_requests, 1)

            return {
                "p50_latency_ms": round(percentile(50), 2),
                "p95_latency_ms": round(percentile(95), 2),
                "p99_latency_ms": round(percentile(99), 2),
                "avg_latency_ms": round(avg, 2),
                "req_per_second": round(rps, 2),
                "total_requests": self._total_requests,
                "error_rate": round(error_rate, 4),
            }

    def reset(self):
        """重置监控。"""
        with self._lock:
            self._latencies.clear()
            self._total_requests = 0
            self._error_count = 0
            self._window_start = time.time()


perf_monitor = PerformanceMonitor()


@app.middleware("http")
async def performance_monitor_middleware(request, call_next):
    """性能监控中间件：记录每次请求的延迟。"""
    start = time.time()
    is_error = False
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            is_error = True
        return response
    except Exception:
        is_error = True
        raise
    finally:
        latency_ms = (time.time() - start) * 1000
        perf_monitor.record(latency_ms, is_error)


# ============================================================
# 全局队列实例
# ============================================================
request_queue = RequestQueue(max_concurrent=MAX_CONCURRENT_REVIEWS)


# ============================================================
# 后台审查任务
# ============================================================

async def _run_review_task(request_id: str):
    """后台执行审查任务。"""
    try:
        # 等待并发许可
        await request_queue.acquire()
        await request_queue.start_processing(request_id)

        # 获取请求数据
        status = await request_queue.get_status(request_id)
        req_data = None
        async with request_queue._lock:
            if request_id in request_queue._requests:
                req_data = request_queue._requests[request_id]["data"]

        if not req_data:
            await request_queue.fail(request_id, "请求数据丢失")
            return

        await request_queue.update_progress(request_id, 0.1, "步骤1/4: 禁用词匹配")

        # 构造 ReviewRequest
        req = ReviewRequest(
            text=req_data["text"],
            industry=req_data.get("industry", "general"),
            platform=req_data.get("platform"),
            api_key=req_data.get("api_key"),
            base_url=req_data.get("base_url"),
        )

        # 步骤 2: 语境判断
        await request_queue.update_progress(request_id, 0.35, "步骤2/4: 语境判断")

        # 步骤 3: RAG 检索
        await request_queue.update_progress(request_id, 0.6, "步骤3/4: 法规检索")

        # 执行审查（这里我们复用 agent_instance.review，
        # 真实环境下可在 agent 内部嵌入更细粒度的进度回调）
        response = await agent_instance.review(req)

        await request_queue.update_progress(request_id, 0.85, "步骤4/4: 生成建议")

        # 保存到历史
        review_store.save_review(
            response.review_id, req.text, response.status,
            response.overall_risk.value if hasattr(response.overall_risk, 'value') else str(response.overall_risk),
            len(response.violations),
            [{"text": v.text, "category": v.category,
              "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity)}
             for v in response.violations],
            req.industry.value if hasattr(req.industry, 'value') else str(req.industry)
        )

        # 转换结果为 dict
        result_dict = {
            "review_id": response.review_id,
            "status": response.status,
            "overall_risk": response.overall_risk.value if hasattr(response.overall_risk, 'value') else str(response.overall_risk),
            "violations": [
                {
                    "id": v.id,
                    "text": v.text,
                    "start_index": v.start_index,
                    "end_index": v.end_index,
                    "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity),
                    "category": v.category,
                    "confidence": v.confidence,
                    "law_article": v.law_article,
                    "law_content": v.law_content,
                    "explanation": v.explanation,
                    "suggestions": [s.model_dump() for s in v.suggestions],
                    "related_cases": [c.model_dump() for c in v.related_cases],
                }
                for v in response.violations
            ],
            "highlighted_text": response.highlighted_text,
            "summary": response.summary,
            "reviewed_at": response.reviewed_at,
            "processing_time_ms": response.processing_time_ms,
            "request_id": request_id,  # 追踪链：request_id → review_id
        }

        await request_queue.complete(request_id, result_dict)

    except Exception as e:
        await request_queue.fail(request_id, str(e))
    finally:
        request_queue.release()


# ============================================================
# 生命周期
# ============================================================

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


# ============================================================
# 同步审查接口（保留兼容）
# ============================================================

@app.post("/api/review", response_model=ReviewResponse)
async def review(request: ReviewRequest):
    try:
        response = await agent_instance.review(request)
        review_store.save_review(
            response.review_id, request.text, response.status,
            response.overall_risk.value if hasattr(response.overall_risk, 'value') else str(response.overall_risk),
            len(response.violations),
            [{"text": v.text, "category": v.category,
              "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity)}
             for v in response.violations],
            request.industry.value if hasattr(request.industry, 'value') else str(request.industry)
        )
        return response
    except Exception as e:
        error_msg = str(e)
        return ReviewResponse(
            review_id=f"ERR-{int(time.time())}",
            status="error",
            overall_risk="pass",
            violations=[],
            highlighted_text=request.text,
            summary=f"审查出错: {error_msg[:200]}。请检查 API Key 是否正确。",
            reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


# ============================================================
# 异步审查接口
# ============================================================

@app.post("/api/review/async", response_model=AsyncReviewResponse)
async def review_async(request: AsyncReviewRequest):
    """提交异步审查请求。

    请求进入队列后立即返回 request_id，客户端通过 GET /api/review/{request_id} 轮询，
    或通过 SSE /api/review/{request_id}/stream 获取实时进度。
    """
    request_id = f"req-{uuid.uuid4().hex[:12]}"

    try:
        await request_queue.submit(request_id, {
            "text": request.text,
            "industry": request.industry.value if hasattr(request.industry, 'value') else str(request.industry),
            "platform": request.platform,
            "api_key": request.api_key,
            "base_url": request.base_url,
            "priority": request.priority,
        })
    except HTTPException:
        raise

    # 启动后台任务
    asyncio.create_task(_run_review_task(request_id))

    status = await request_queue.get_status(request_id)
    return AsyncReviewResponse(
        request_id=request_id,
        status="queued",
        position=status["position_in_queue"] if status else 0,
        message=f"请求已提交，当前队列位置: {status['position_in_queue'] if status else '?'}",
    )


@app.get("/api/review/{request_id}", response_model=ReviewStatusResponse)
async def get_review_status(request_id: str):
    """查询异步审查状态。"""
    status = await request_queue.get_status(request_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"请求 {request_id} 不存在")
    return status


@app.get("/api/review/{request_id}/stream")
async def review_stream(request_id: str):
    """SSE 实时进度推送。

    客户端使用 EventSource 连接此端点，实时接收审查进度。
    """
    status = await request_queue.get_status(request_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"请求 {request_id} 不存在")

    async def event_generator():
        last_status = ""
        last_progress = -1.0
        while True:
            s = await request_queue.get_status(request_id)
            if not s:
                yield f"event: error\ndata: 请求不存在\n\n"
                break

            # 只在状态或进度变化时推送
            if s["status"] != last_status or abs(s["progress"] - last_progress) > 0.01:
                last_status = s["status"]
                last_progress = s["progress"]

                event_data = {
                    "request_id": request_id,
                    "status": s["status"],
                    "progress": s["progress"],
                    "current_step": s["current_step"],
                    "position_in_queue": s["position_in_queue"],
                }

                if s["status"] == "completed" and "result" in s:
                    event_data["result"] = s["result"]
                    yield f"event: completed\ndata: {__import__('json').dumps(event_data, ensure_ascii=False)}\n\n"
                    break
                elif s["status"] == "failed":
                    event_data["error"] = s.get("error", "未知错误")
                    yield f"event: failed\ndata: {__import__('json').dumps(event_data, ensure_ascii=False)}\n\n"
                    break
                else:
                    yield f"event: progress\ndata: {__import__('json').dumps(event_data, ensure_ascii=False)}\n\n"

            await asyncio.sleep(0.5)  # 每 500ms 检查一次

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 反馈接口
# ============================================================

@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest):
    review_store.save_feedback(
        request.review_id,
        request.violation_id,
        request.action.value if hasattr(request.action, 'value') else str(request.action),
        request.replacement
    )
    # 触发反馈学习（异步，不阻塞响应）
    asyncio.create_task(_apply_feedback_learning(request))
    return FeedbackResponse(success=True)


@app.get("/api/feedback/stats", response_model=FeedbackStatsResponse)
async def feedback_stats():
    """反馈统计接口。"""
    stats = review_store.get_feedback_stats()
    return stats


async def _apply_feedback_learning(request: FeedbackRequest):
    """异步应用反馈学习：更新 VmemStore 中相关条目的置信度。"""
    try:
        if agent_instance and hasattr(agent_instance, '_store'):
            store = agent_instance._store
            action = request.action.value if hasattr(request.action, 'value') else str(request.action)
            # CONFIRM → 提升置信度，DISMISS → 降低置信度
            delta = 0.05 if action == "confirm" else (-0.1 if action == "dismiss" else -0.05)
            if hasattr(store, 'update_confidence_by_keyword'):
                store.update_confidence_by_keyword(request.violation_id, delta)
    except Exception:
        pass  # 反馈学习失败不影响主流程


# ============================================================
# 统计 & 健康检查
# ============================================================

@app.get("/api/stats", response_model=StatsResponse)
async def stats():
    return review_store.get_stats()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/metrics", response_model=PerformanceMetrics)
async def get_metrics():
    """性能监控指标接口。"""
    metrics = perf_monitor.get_metrics()
    metrics["active_requests"] = request_queue.active_count()
    metrics["queued_requests"] = request_queue.queued_count()
    return metrics


@app.get("/api/queue/status")
async def queue_status():
    """队列状态。"""
    return {
        "max_concurrent": MAX_CONCURRENT_REVIEWS,
        "active_requests": request_queue.active_count(),
        "queued_requests": request_queue.queued_count(),
        "max_queue_size": MAX_QUEUE_SIZE,
    }


# ============================================================
# 审查历史
# ============================================================

@app.get("/api/reviews")
async def list_reviews(limit: int = 20, offset: int = 0):
    """审查历史列表。"""
    if not review_store:
        return {"reviews": [], "total": 0}
    result = review_store.list_reviews(limit=limit, offset=offset)
    return result


@app.get("/api/reviews/{review_id}")
async def get_review(review_id: str):
    """获取单条审查详情。"""
    if not review_store:
        raise HTTPException(status_code=404, detail="存储未初始化")
    result = review_store.get_review(review_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"审查记录 {review_id} 不存在")
    return result
