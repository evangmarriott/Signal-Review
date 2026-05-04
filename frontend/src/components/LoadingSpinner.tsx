import type { ReactElement } from "react";

export function LoadingSpinner(): ReactElement {
  return (
    <section className="rounded-[24px] border border-slate-200 bg-white/90 p-8 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
      <div className="flex items-center gap-4">
        <div className="h-11 w-11 animate-spin rounded-full border-4 border-slate-200 border-t-teal-500" />
        <div>
          <p className="text-base font-semibold text-slate-950">Reviewing pull request</p>
          <p className="mt-1 text-sm text-slate-500">
            Fetching the diff, calling Claude, and applying Signal Filter.
          </p>
        </div>
      </div>
    </section>
  );
}
