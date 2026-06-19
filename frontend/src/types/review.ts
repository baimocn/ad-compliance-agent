export type Severity = "high" | "medium" | "low" | "pass";
export type Industry =
  | "general"
  | "food"
  | "cosmetic"
  | "medicine"
  | "education"
  | "real_estate"
  | "finance"
  | "ecommerce";
export type FeedbackAction = "confirm" | "modify" | "dismiss";

export interface Suggestion {
  original: string;
  replacement: string;
  reason: string;
}

export interface RelatedCase {
  title: string;
  penalty: string;
  article: string;
}

export interface Violation {
  id: string;
  text: string;
  startIndex: number;
  endIndex: number;
  severity: Severity;
  category: string;
  lawArticle: string;
  lawContent: string;
  explanation: string;
  suggestions: Suggestion[];
  relatedCases?: RelatedCase[];
}

export interface PipelineStep {
  step: number;
  name: string;
  status: "completed" | "skipped";
  detail: string;
  icon: string;
}

export interface ReviewRequest {
  text: string;
  industry: Industry;
  platform?: string;
}

export interface ReviewResponse {
  reviewId: string;
  status: "safe" | "violation_found";
  overallRisk: Severity;
  violations: Violation[];
  highlightedText: string;
  summary: string;
  reviewedAt: string;
  processingTimeMs?: number;
  tokenUsage?: Record<string, number>;
  pipelineSteps: PipelineStep[];
}

export interface FeedbackRequest {
  reviewId: string;
  violationId: string;
  action: FeedbackAction;
  replacement?: string;
}

export interface FeedbackResponse {
  success: boolean;
  updatedText?: string;
  updatedViolations?: Violation[];
}

export interface StatsResponse {
  totalReviews: number;
  totalViolations: number;
  violationByCategory: { category: string; count: number }[];
  violationBySeverity: { severity: Severity; count: number }[];
  recentReviews: {
    reviewId: string;
    text: string;
    status: string;
    overallRisk: Severity;
    violationCount: number;
  }[];
}
