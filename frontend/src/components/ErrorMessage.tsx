import type { ReactElement } from "react";

interface ErrorMessageProps {
  message: string;
}

export function ErrorMessage({ message }: ErrorMessageProps): ReactElement {
  return (
    <section className="rounded-[24px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800 shadow-[0_10px_30px_rgba(244,63,94,0.08)]">
      <p className="font-semibold">Review failed</p>
      <p className="mt-1 leading-6">{message}</p>
    </section>
  );
}
