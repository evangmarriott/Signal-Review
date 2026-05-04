import type { ReactElement } from "react";

import { ErrorMessage } from "@/components/ErrorMessage";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ReviewForm } from "@/components/ReviewForm";
import { ReviewResult } from "@/components/ReviewResult";
import { useReview } from "@/hooks/useReview";

export function App(): ReactElement {
  const { submitReview, result, isLoading, error, reset } = useReview();

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.16),_transparent_30%),linear-gradient(180deg,_#f6fbfa_0%,_#eef4f7_100%)] px-4 py-8 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
        <header className="rounded-[28px] border border-white/70 bg-white/85 p-8 shadow-[0_20px_80px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="mb-5 flex items-center gap-3">
            <span className="rounded-full border border-teal-200 bg-teal-50 px-4 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-teal-700">
              MVP
            </span>
          </div>
          <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
            <div className="space-y-4">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.28em] text-slate-500">
                  SignalReview
                </p>
                <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
                  Review pull requests without drowning in AI comments.
                </h1>
              </div>
              <p className="max-w-3xl text-base leading-7 text-slate-600 sm:text-lg">
                AI PR review without the noise. Paste a public GitHub PR URL, add optional repo
                context, and get severity/confidence-ranked comments with low-signal feedback
                hidden by default.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-slate-950 p-5 text-sm text-slate-200 shadow-[0_12px_32px_rgba(15,23,42,0.22)]">
              <p className="font-semibold text-white">Low-noise by design</p>
              <p className="mt-2 leading-6 text-slate-300">
                Every issue must explain the problem, why it matters, and the suggested fix.
                Signal Filter then separates visible high-signal comments from muted lower-signal
                ones.
              </p>
            </div>
          </div>
        </header>

        <section className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-6">
            <ReviewForm
              isLoading={isLoading}
              onReset={reset}
              onSubmit={async (request) => {
                await submitReview(request);
              }}
            />

            <section className="rounded-[24px] border border-slate-200 bg-white/90 p-6 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
              <h2 className="text-lg font-semibold text-slate-950">Why context matters</h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                A PR diff only shows changed lines. Repo context helps avoid false positives by
                showing middleware, tests, types, and team conventions. For this MVP, context is
                pasted manually. In production, a GitHub App would fetch it automatically.
              </p>
            </section>
          </div>

          <div className="space-y-6">
            {error ? <ErrorMessage message={error} /> : null}
            {isLoading ? <LoadingSpinner /> : null}
            {!isLoading && result === null ? (
              <section className="rounded-[24px] border border-dashed border-slate-300 bg-white/70 p-8 text-center shadow-[0_18px_50px_rgba(15,23,42,0.04)]">
                <p className="text-lg font-semibold text-slate-900">Your review will appear here.</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  SignalReview will fetch the PR diff, analyze it, and show only the highest-signal
                  comments by default.
                </p>
              </section>
            ) : null}
            {result !== null ? <ReviewResult result={result} /> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
