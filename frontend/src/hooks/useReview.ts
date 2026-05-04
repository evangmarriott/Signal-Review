import { useMutation } from "@tanstack/react-query";

import { submitPRReview } from "@/api/review";
import type { PRReviewRequest, PRReviewResult } from "@/types/review";

interface UseReviewResult {
  submitReview: (request: PRReviewRequest) => Promise<PRReviewResult>;
  result: PRReviewResult | null;
  isLoading: boolean;
  error: string | null;
  reset: () => void;
}

export function useReview(): UseReviewResult {
  const mutation = useMutation({
    mutationFn: submitPRReview,
  });
  const reset = (): void => {
    mutation.reset();
  };

  return {
    submitReview: mutation.mutateAsync,
    result: mutation.data ?? null,
    isLoading: mutation.isPending,
    error: mutation.error instanceof Error ? mutation.error.message : null,
    reset,
  };
}
