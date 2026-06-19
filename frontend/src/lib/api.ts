import {
  ReviewRequest,
  ReviewResponse,
  FeedbackRequest,
  FeedbackResponse,
  StatsResponse,
} from "@/types/review";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getStoredConfig() {
  if (typeof window === "undefined") return {};
  return {
    apiKey: localStorage.getItem("ad_agent_api_key") || "",
    baseUrl: localStorage.getItem("ad_agent_base_url") || "",
  };
}

/** Convert snake_case keys to camelCase recursively */
function toCamelCase(obj: any): any {
  if (Array.isArray(obj)) return obj.map(toCamelCase);
  if (obj !== null && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj).map(([key, value]) => [
        key.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
        toCamelCase(value),
      ])
    );
  }
  return obj;
}

export async function submitReview(req: ReviewRequest): Promise<ReviewResponse> {
  const config = getStoredConfig();
  const res = await fetch(`${API_BASE}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: req.text,
      industry: req.industry,
      platform: req.platform,
      api_key: config.apiKey || undefined,
      base_url: config.baseUrl || undefined,
    }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`Review failed: ${res.status}`);
  const data = await res.json();
  return toCamelCase(data) as ReviewResponse;
}

export async function submitFeedback(req: FeedbackRequest): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      review_id: req.reviewId,
      violation_id: req.violationId,
      action: req.action,
      replacement: req.replacement,
    }),
  });
  if (!res.ok) throw new Error(`Feedback failed: ${res.status}`);
  return res.json();
}

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error(`Stats failed: ${res.status}`);
  return res.json();
}

// ============================================================
// 异步审查接口
// ============================================================

export interface AsyncReviewRequest {
  text: string;
  industry: string;
  platform?: string;
  priority?: number;
}

export interface AsyncReviewResponse {
  requestId: string;
  status: "queued" | "processing" | "completed" | "failed";
  position: number;
  message: string;
}

export interface ReviewStatusResponse {
  requestId: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  currentStep: string;
  queuedAt: string;
  startedAt: string;
  completedAt: string;
  positionInQueue: number;
  result?: any;
  error?: string;
}

export async function submitAsyncReview(req: AsyncReviewRequest): Promise<AsyncReviewResponse> {
  const config = getStoredConfig();
  const res = await fetch(`${API_BASE}/api/review/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: req.text,
      industry: req.industry,
      platform: req.platform,
      priority: req.priority ?? 5,
      api_key: config.apiKey || undefined,
      base_url: config.baseUrl || undefined,
    }),
  });
  if (!res.ok) throw new Error(`Async review failed: ${res.status}`);
  return toCamelCase(await res.json()) as AsyncReviewResponse;
}

export async function getReviewStatus(requestId: string): Promise<ReviewStatusResponse> {
  const res = await fetch(`${API_BASE}/api/review/${requestId}`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return toCamelCase(await res.json()) as ReviewStatusResponse;
}

/**
 * SSE 实时进度推送。
 * 使用 EventSource 连接 /api/review/{requestId}/stream
 */
export function streamReviewProgress(
  requestId: string,
  onProgress: (data: ReviewStatusResponse) => void,
  onCompleted: (result: any) => void,
  onFailed: (error: string) => void,
): () => void {
  const es = new EventSource(`${API_BASE}/api/review/${requestId}/stream`);

  es.addEventListener("progress", (event: MessageEvent) => {
    const data = toCamelCase(JSON.parse(event.data));
    onProgress(data as ReviewStatusResponse);
  });

  es.addEventListener("completed", (event: MessageEvent) => {
    const data = toCamelCase(JSON.parse(event.data));
    onCompleted(data.result);
    es.close();
  });

  es.addEventListener("failed", (event: MessageEvent) => {
    const data = JSON.parse(event.data);
    onFailed(data.error || "未知错误");
    es.close();
  });

  es.onerror = () => {
    // 连接错误时关闭
    es.close();
  };

  return () => es.close();
}

// ============================================================
// 审查历史接口
// ============================================================

export interface ReviewListItem {
  reviewId: string;
  textPreview: string;
  status: string;
  overallRisk: string;
  violationCount: number;
  industry: string;
  createdAt: string;
}

export interface ReviewListResponse {
  reviews: ReviewListItem[];
  total: number;
  limit: number;
  offset: number;
}

export async function listReviews(limit = 20, offset = 0): Promise<ReviewListResponse> {
  const res = await fetch(`${API_BASE}/api/reviews?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`List reviews failed: ${res.status}`);
  return toCamelCase(await res.json()) as ReviewListResponse;
}

export async function getReviewDetail(reviewId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/reviews/${reviewId}`);
  if (!res.ok) throw new Error(`Get review failed: ${res.status}`);
  return toCamelCase(await res.json());
}

// ============================================================
// 反馈统计接口
// ============================================================

export interface FeedbackStatsResponse {
  totalFeedback: number;
  confirmCount: number;
  modifyCount: number;
  dismissCount: number;
  wordFeedback: any[];
  categoryFeedback: any[];
  learningAdjustments: any[];
}

export async function getFeedbackStats(): Promise<FeedbackStatsResponse> {
  const res = await fetch(`${API_BASE}/api/feedback/stats`);
  if (!res.ok) throw new Error(`Feedback stats failed: ${res.status}`);
  return toCamelCase(await res.json()) as FeedbackStatsResponse;
}

// ============================================================
// 性能监控接口
// ============================================================

export interface PerformanceMetrics {
  p50LatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  avgLatencyMs: number;
  reqPerSecond: number;
  totalRequests: number;
  activeRequests: number;
  queuedRequests: number;
  errorRate: number;
}

export async function getPerformanceMetrics(): Promise<PerformanceMetrics> {
  const res = await fetch(`${API_BASE}/api/metrics`);
  if (!res.ok) throw new Error(`Metrics failed: ${res.status}`);
  return toCamelCase(await res.json()) as PerformanceMetrics;
}
