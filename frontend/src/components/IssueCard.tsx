import type { ReactElement } from "react";

import { Badge } from "@/components/Badge";
import type {
  ReviewCategory,
  ReviewComment,
  ReviewConfidence,
  ReviewSeverity,
} from "@/types/review";

interface IssueCardProps {
  comment: ReviewComment;
  muted?: boolean;
}

const severityTones: Record<ReviewSeverity, "rose" | "amber" | "sky" | "slate"> = {
  critical: "rose",
  high: "rose",
  medium: "amber",
  low: "slate",
};

const confidenceTones: Record<ReviewConfidence, "emerald" | "amber" | "slate"> = {
  high: "emerald",
  medium: "amber",
  low: "slate",
};

const categoryTones: Record<ReviewCategory, "teal" | "sky" | "amber" | "slate"> = {
  security: "teal",
  logic: "sky",
  tests: "amber",
  performance: "amber",
  readability: "slate",
  style: "slate",
};

export function IssueCard({ comment, muted = false }: IssueCardProps): ReactElement {
  const wrapperClasses = muted
    ? "border-slate-200 bg-slate-50/90 text-slate-500"
    : "border-slate-200 bg-white text-slate-700";
  const location = `${comment.file ?? "Unknown file"}${comment.line !== null ? `:${comment.line.toString()}` : ""}`;

  return (
    <article
      className={`rounded-[22px] border p-5 shadow-[0_12px_40px_rgba(15,23,42,0.05)] ${wrapperClasses}`}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-950">{comment.title}</h3>
          <p className="mt-1 text-sm text-slate-500">{location}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge
            label={`${comment.severity} severity`}
            tone={severityTones[comment.severity]}
          />
          <Badge
            label={`${comment.confidence} confidence`}
            tone={confidenceTones[comment.confidence]}
          />
          <Badge label={comment.category} tone={categoryTones[comment.category]} />
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        <section>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Problem
          </p>
          <p className="mt-2 text-sm leading-6">{comment.problem}</p>
        </section>
        <section>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Why It Matters
          </p>
          <p className="mt-2 text-sm leading-6">{comment.why_it_matters}</p>
        </section>
        <section>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Suggested Fix
          </p>
          <p className="mt-2 text-sm leading-6">{comment.suggestion}</p>
        </section>
        {comment.code_suggestion ? (
          <section>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Code Suggestion
            </p>
            <pre className="mt-2 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">
              <code>{comment.code_suggestion}</code>
            </pre>
          </section>
        ) : null}
      </div>
    </article>
  );
}
