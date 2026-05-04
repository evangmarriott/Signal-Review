export type ReviewFocus =
  | "security"
  | "logic"
  | "tests"
  | "performance"
  | "readability"
  | "style";

export type ReviewStrictness = "quiet" | "balanced" | "strict";

export type ReviewCategory =
  | "security"
  | "logic"
  | "tests"
  | "performance"
  | "readability"
  | "style";

export type ReviewSeverity = "critical" | "high" | "medium" | "low";

export type ReviewConfidence = "high" | "medium" | "low";

export type MergeRecommendation = "approve" | "comment" | "request_changes";

export type OverallRisk = "low" | "medium" | "high" | "critical";

export interface ReviewComment {
  title: string;
  file: string | null;
  line: number | null;
  category: ReviewCategory;
  severity: ReviewSeverity;
  confidence: ReviewConfidence;
  problem: string;
  why_it_matters: string;
  suggestion: string;
  code_suggestion: string | null;
  is_hidden_by_default: boolean;
}

export interface FileSummary {
  filename: string;
  change_type: string;
  risk_level: OverallRisk;
  summary: string;
}

export interface PRReviewRequest {
  github_url: string;
  repo_context: string | null;
  focus_areas: ReviewFocus[];
  strictness: ReviewStrictness;
}

export interface PRReviewResult {
  pr_title: string;
  pr_author: string;
  pr_url: string;
  overall_risk: OverallRisk;
  merge_recommendation: MergeRecommendation;
  summary: string;
  visible_comments: ReviewComment[];
  hidden_comments: ReviewComment[];
  total_comments: number;
  visible_comments_count: number;
  hidden_comments_count: number;
  signal_filter_summary: string;
  file_summaries: FileSummary[];
}

export interface ErrorResponse {
  error: string;
  detail: string;
  status_code: number;
}
