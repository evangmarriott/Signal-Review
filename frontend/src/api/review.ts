import { postJson } from "@/api/client";
import type { PRReviewRequest, PRReviewResult } from "@/types/review";

export function submitPRReview(request: PRReviewRequest): Promise<PRReviewResult> {
  return postJson<PRReviewResult>("/api/review", request);
}
