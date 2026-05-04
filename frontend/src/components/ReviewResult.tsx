import type { ReactElement } from "react";
import { useState } from "react";

import { IssueCard } from "@/components/IssueCard";
import { SummaryCard } from "@/components/SummaryCard";
import type { PRReviewResult } from "@/types/review";

interface ReviewResultProps {
  result: PRReviewResult;
}

export function ReviewResult({ result }: ReviewResultProps): ReactElement {
  const [showHiddenComments, setShowHiddenComments] = useState(false);

  return (
    <div className="space-y-6">
      <SummaryCard result={result} />

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-950">Visible comments</h2>
          <p className="text-sm text-slate-500">
            {result.visible_comments_count} shown by default
          </p>
        </div>
        {result.visible_comments.length > 0 ? (
          <div className="space-y-4">
            {result.visible_comments.map((comment) => (
              <IssueCard
                key={[
                  comment.title,
                  comment.file ?? "unknown",
                  comment.line?.toString() ?? "na",
                ].join("-")}
                comment={comment}
              />
            ))}
          </div>
        ) : (
          <section className="rounded-[24px] border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.04)]">
            No high-signal comments were visible for the selected strictness.
          </section>
        )}
      </section>

      {result.hidden_comments_count > 0 ? (
        <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">
                {result.hidden_comments_count} lower-signal comments hidden by Signal Filter.
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Expand them when you want broader AI coverage.
              </p>
            </div>
            <button
              className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-950 hover:text-slate-950"
              onClick={() => {
                setShowHiddenComments((current) => !current);
              }}
              type="button"
            >
              {showHiddenComments ? "Hide hidden comments" : "Show hidden comments"}
            </button>
          </div>

          {showHiddenComments ? (
            <div className="mt-5 space-y-4">
              {result.hidden_comments.map((comment) => (
                <IssueCard
                  key={[
                    comment.title,
                    comment.file ?? "unknown",
                    comment.line?.toString() ?? "na",
                    "hidden",
                  ].join("-")}
                  comment={comment}
                  muted
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-950">File summaries</h2>
          <p className="text-sm text-slate-500">{result.file_summaries.length} files summarized</p>
        </div>
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  File
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Change Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Risk
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Summary
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {result.file_summaries.map((fileSummary) => (
                <tr key={`${fileSummary.filename}-${fileSummary.change_type}`}>
                  <td className="px-4 py-4 align-top text-sm font-medium text-slate-900">
                    {fileSummary.filename}
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-600">
                    {fileSummary.change_type}
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-600">
                    {fileSummary.risk_level}
                  </td>
                  <td className="px-4 py-4 align-top text-sm leading-6 text-slate-600">
                    {fileSummary.summary}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
