import {
  ReviewRequest,
  ReviewResponse,
  FeedbackRequest,
  FeedbackResponse,
  StatsResponse,
} from "@/types/review";

const API_BASE = "http://localhost:8001";

function getStoredConfig() {
  if (typeof window === "undefined") return {};
  return {
    apiKey: localStorage.getItem("ad_agent_api_key") || "",
    baseUrl: localStorage.getItem("ad_agent_base_url") || "",
    model: localStorage.getItem("ad_agent_model") || "",
  };
}

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ad_agent_token");
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (token) return { Authorization: `Bearer ${token}` };
  return {};
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

// ── Auth ──────────────────────────────────────────────────────

export async function login(username: string, password: string): Promise<{ token: string; username: string; user_id: number }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok || !data.success) throw new Error(data.detail || data.error || "登录失败");
  return data;
}

export async function register(username: string, password: string): Promise<{ token: string; username: string; user_id: number }> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok || !data.success) throw new Error(data.detail || data.error || "注册失败");
  return data;
}

export async function getMe(): Promise<{ user_id: number; username: string }> {
  const res = await fetch(`${API_BASE}/api/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error("未登录");
  const data = await res.json();
  if (!data.success) throw new Error("未登录");
  return data;
}

export async function getMyReviews(limit = 50, risk?: string, query?: string, dateFrom?: string, dateTo?: string): Promise<{ reviews: any[] }> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (risk && risk !== "all") params.set("risk", risk)
  if (query) params.set("query", query)
  if (dateFrom) params.set("date_from", dateFrom)
  if (dateTo) params.set("date_to", dateTo)
  const res = await fetch(`${API_BASE}/api/my-reviews?${params}`, { headers: authHeaders() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err: any = new Error(data.detail || "获取历史记录失败");
    err.status = res.status;
    throw err;
  }
  return data;
}

export async function testConnection(apiKey: string, baseUrl: string, model: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/test-connection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, base_url: baseUrl, model }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "连接测试失败");
  return data;
}

export async function forgotPassword(username: string): Promise<{ reset_token: string }> {
  const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  });
  const data = await res.json();
  if (!res.ok || !data.success) throw new Error(data.detail || "发送失败");
  return data;
}

export async function resetPassword(username: string, resetToken: string, newPassword: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, reset_token: resetToken, new_password: newPassword }),
  });
  const data = await res.json();
  if (!res.ok || !data.success) throw new Error(data.detail || "重置失败");
}

export async function deleteAccount(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/account`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.success) throw new Error(data.detail || "删除失败");
}

export async function getUsage(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/usage`, { headers: authHeaders() });
  if (!res.ok) throw new Error("获取用量失败");
  return res.json();
}

// ── Core API ──────────────────────────────────────────────────

export async function submitReview(req: ReviewRequest): Promise<ReviewResponse> {
  const config = getStoredConfig();
  const res = await fetch(`${API_BASE}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      text: req.text,
      industry: req.industry,
      platform: req.platform,
      api_key: config.apiKey || undefined,
      base_url: config.baseUrl || undefined,
      model: config.model || undefined,
    }),
    signal: AbortSignal.timeout(120000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err: any = new Error(data.detail || `审查失败 (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return toCamelCase(data) as ReviewResponse;
}

export async function submitFeedback(req: FeedbackRequest): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
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
  const res = await fetch(`${API_BASE}/api/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Stats failed: ${res.status}`);
  return res.json();
}
