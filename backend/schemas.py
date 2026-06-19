"""广告法合规审查 Agent — 统一数据模型"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PASS = "pass"


class Industry(str, Enum):
    GENERAL = "general"
    FOOD = "food"
    COSMETIC = "cosmetic"
    MEDICINE = "medicine"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    FINANCE = "finance"
    ECOMMERCE = "ecommerce"
    MANUFACTURING = "manufacturing"
    HEALTHCARE = "healthcare"
    TECHNOLOGY = "technology"
    FOOD_SERVICE = "food_service"
    BEAUTY = "beauty"
    CORPORATE = "corporate"


class FeedbackAction(str, Enum):
    CONFIRM = "confirm"
    MODIFY = "modify"
    DISMISS = "dismiss"


class BannedWordHit(BaseModel):
    word: str
    category: str
    position: tuple[int, int]
    regulation_ref: str


class ContextJudgment(BaseModel):
    is_violation: bool
    reasoning: str
    confidence: float = Field(ge=0, le=1)
    # v2 新增：多维度置信度
    violation_type_confidence: float = Field(default=0.5, ge=0, le=1, description="违规类型判定置信度")
    severity_confidence: float = Field(default=0.5, ge=0, le=1, description="风险等级判定置信度")
    context_relevance: float = Field(default=0.5, ge=0, le=1, description="语境相关性（营销意图强度）")
    # v2 新增：结构化推理
    evidence: list[str] = Field(default_factory=list, description="支撑判断的证据点")
    mitigating_factors: list[str] = Field(default_factory=list, description="可减轻的因素（如限定词、客观陈述）")
    suggested_severity: str = Field(default="medium", description="建议风险等级: high/medium/low/pass")
    violation_type: str = Field(default="", description="判定的违规类型")


class RegulationCitation(BaseModel):
    law_name: str
    article: str
    content: str
    relevance_score: float


class Suggestion(BaseModel):
    original: str
    replacement: str
    reason: str


class RelatedCase(BaseModel):
    title: str
    penalty: str
    article: str


class Violation(BaseModel):
    id: str
    text: str
    start_index: int
    end_index: int
    severity: RiskLevel
    category: str
    confidence: float = Field(default=0.5, ge=0, le=1, description="Agent 判断置信度")
    law_article: str
    law_content: str
    explanation: str
    suggestions: list[Suggestion] = []
    related_cases: list[RelatedCase] = []


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    industry: Industry = Industry.GENERAL
    platform: Optional[str] = None
    api_key: Optional[str] = Field(default=None, description="LLM API Key，从 .env 读取或前端传入")
    base_url: Optional[str] = Field(default=None, description="LLM API Base URL")


class PipelineStep(BaseModel):
    step: int
    name: str
    status: str  # "completed" | "skipped"
    detail: str
    icon: str  # emoji


class ReviewResponse(BaseModel):
    review_id: str
    status: str  # "safe" | "violation_found"
    overall_risk: RiskLevel
    violations: list[Violation] = []
    highlighted_text: str
    summary: str
    reviewed_at: str
    processing_time_ms: Optional[int] = None
    token_usage: Optional[dict] = None
    pipeline_steps: list[PipelineStep] = []


class FeedbackRequest(BaseModel):
    review_id: str
    violation_id: str
    action: FeedbackAction
    replacement: Optional[str] = None


class FeedbackResponse(BaseModel):
    success: bool
    updated_text: Optional[str] = None
    updated_violations: list[Violation] = []


class StatsResponse(BaseModel):
    model_config = {"extra": "allow"}
    totalReviews: int = 0
    totalViolations: int = 0
    violationByCategory: list[dict] = []
    violationBySeverity: list[dict] = []
    recentReviews: list[dict] = []


# ============================================================
# 异步审查 & 并发相关数据模型
# ============================================================

class AsyncReviewRequest(BaseModel):
    """异步审查请求"""
    text: str = Field(min_length=1, max_length=5000)
    industry: Industry = Industry.GENERAL
    platform: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10, description="优先级，1最高，10最低")


class AsyncReviewResponse(BaseModel):
    """异步审查提交响应"""
    request_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    position: int = 0
    message: str = ""


class ReviewStatusResponse(BaseModel):
    """审查状态查询响应"""
    request_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    progress: float = Field(default=0.0, ge=0, le=1, description="处理进度 0~1")
    current_step: str = ""
    queued_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    position_in_queue: int = 0


class FeedbackStatsResponse(BaseModel):
    """反馈统计响应"""
    total_feedback: int = 0
    confirm_count: int = 0
    modify_count: int = 0
    dismiss_count: int = 0
    word_feedback: list[dict] = []  # 按禁用词分组的反馈统计
    category_feedback: list[dict] = []  # 按违规类型分组的反馈统计
    learning_adjustments: list[dict] = []  # 置信度调整记录


class PerformanceMetrics(BaseModel):
    """性能监控指标"""
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    req_per_second: float = 0.0
    total_requests: int = 0
    active_requests: int = 0
    queued_requests: int = 0
    error_rate: float = 0.0


# 行业中英文映射
INDUSTRY_MAP = {
    "general": "通用",
    "food": "食品",
    "cosmetic": "化妆品",
    "medicine": "医药",
    "education": "教育",
    "real_estate": "房地产",
    "finance": "金融",
    "ecommerce": "电商",
}
