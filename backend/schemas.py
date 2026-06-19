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
