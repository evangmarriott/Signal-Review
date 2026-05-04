import type { ReactElement } from "react";

interface BadgeProps {
  label: string;
  tone: "slate" | "teal" | "amber" | "rose" | "sky" | "emerald";
}

const toneClasses: Record<BadgeProps["tone"], string> = {
  slate: "border-slate-200 bg-slate-100 text-slate-700",
  teal: "border-teal-200 bg-teal-50 text-teal-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  rose: "border-rose-200 bg-rose-50 text-rose-700",
  sky: "border-sky-200 bg-sky-50 text-sky-700",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

export function Badge({ label, tone }: BadgeProps): ReactElement {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}
