import type { ReactElement } from "react";

import { Badge } from "@/components/Badge";
import type { MergeRecommendation, OverallRisk, PRReviewResult } from "@/types/review";

interface SummaryCardProps {
  result: PRReviewResult;
}

const riskTone: Record<OverallRisk, "rose" | "amber" | "sky" | "emerald"> = {
  critical: "rose",
  high: "rose",
  medium: "amber",
  low: "emerald",
};

const recommendationTone: Record<MergeRecommendation, "rose" | "amber" | "emerald"> = {
  request_changes: "rose",
  comment: "amber",
  approve: "emerald",
};

export function SummaryCard({ result }: SummaryCardProps): ReactElement {
  return (
    <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-400">
            Review Summary
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            {result.pr_title}
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            by {result.pr_author} ·{" "}
            <a
              className="font-medium text-teal-700 underline decoration-teal-300 underline-offset-4"
              href={result.pr_url}
              rel="noreferrer"
              target="_blank"
            >
              Open PR
            </a>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge label={`risk ${result.overall_risk}`} tone={riskTone[result.overall_risk]} />
          <Badge
            label={result.merge_recommendation.replace("_", " ")}
            tone={recommendationTone[result.merge_recommendation]}
          />
        </div>
      </div>

      <p className="mt-5 text-sm leading-7 text-slate-600">{result.summary}</p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total comments" value={result.total_comments} />
        <Metric label="Visible comments" value={result.visible_comments_count} />
        <Metric label="Hidden comments" value={result.hidden_comments_count} />
        <Metric label="Signal Filter" value={result.signal_filter_summary} compact />
      </div>
    </section>
  );
}

interface MetricProps {
  label: string;
  value: number | string;
  compact?: boolean;
}

function Metric({ label, value, compact = false }: MetricProps): ReactElement {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p
        className={`mt-2 ${compact ? "text-sm leading-6 text-slate-600" : "text-2xl font-semibold text-slate-950"}`}
      >
        {value}
      </p>
    </div>
  );
}
