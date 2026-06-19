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
