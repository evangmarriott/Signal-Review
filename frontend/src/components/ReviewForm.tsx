import type { FormEvent, ReactElement } from "react";
import { useState } from "react";

import type { PRReviewRequest, ReviewFocus, ReviewStrictness } from "@/types/review";

interface ReviewFormProps {
  isLoading: boolean;
  onSubmit: (request: PRReviewRequest) => Promise<void>;
  onReset: () => void;
}

interface FormState {
  githubUrl: string;
  repoContext: string;
  focusAreas: ReviewFocus[];
  strictness: ReviewStrictness;
}

const defaultFocusAreas: ReviewFocus[] = ["security", "logic", "tests"];
const allFocusAreas: ReviewFocus[] = [
  "security",
  "logic",
  "tests",
  "performance",
  "readability",
  "style",
];
const sampleRepoContext = `middleware/auth.ts:
export function requireAuth(req, res, next) {
  if (!req.user) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

Team rule:
Any endpoint returning user data must check object-level authorization. Authentication confirms the user is logged in, but does not confirm the user can access a specific user's data.`;

export function ReviewForm({ isLoading, onSubmit, onReset }: ReviewFormProps): ReactElement {
  const [formState, setFormState] = useState<FormState>({
    githubUrl: "",
    repoContext: "",
    focusAreas: [...defaultFocusAreas],
    strictness: "balanced",
  });
  const [urlError, setUrlError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (!isGitHubPullRequestUrl(formState.githubUrl)) {
      setUrlError("Enter a valid GitHub pull request URL.");
      return;
    }

    setUrlError(null);
    await onSubmit({
      github_url: formState.githubUrl.trim(),
      repo_context: formState.repoContext.trim() ? formState.repoContext.trim() : null,
      focus_areas: formState.focusAreas,
      strictness: formState.strictness,
    });
  }

  function toggleFocusArea(focusArea: ReviewFocus): void {
    setFormState((current) => {
      if (current.focusAreas.includes(focusArea)) {
        return {
          ...current,
          focusAreas: current.focusAreas.filter((item) => item !== focusArea),
        };
      }
      return {
        ...current,
        focusAreas: [...current.focusAreas, focusArea],
      };
    });
  }

  return (
    <section className="rounded-[24px] border border-slate-200 bg-white/90 p-6 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
      <div className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-400">
          Start Review
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
          Paste a public GitHub PR URL
        </h2>
      </div>

      <form
        className="space-y-6"
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        <div className="space-y-2">
          <label className="block text-sm font-semibold text-slate-800" htmlFor="github-url">
            GitHub PR URL
          </label>
          <input
            className={`w-full rounded-2xl border bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition ${urlError ? "border-rose-300 ring-2 ring-rose-100" : "border-slate-200 focus:border-teal-400 focus:bg-white"}`}
            id="github-url"
            onChange={(event) => {
              const value = event.target.value;
              setFormState((current) => ({ ...current, githubUrl: value }));
              if (value.trim() === "" || isGitHubPullRequestUrl(value)) {
                setUrlError(null);
              }
            }}
            placeholder="https://github.com/owner/repo/pull/123"
            type="url"
            value={formState.githubUrl}
          />
          {urlError ? <p className="text-sm text-rose-600">{urlError}</p> : null}
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-semibold text-slate-800" htmlFor="repo-context">
            Optional repo context
          </label>
          <textarea
            className="min-h-48 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-teal-400 focus:bg-white"
            id="repo-context"
            onChange={(event) => {
              setFormState((current) => ({ ...current, repoContext: event.target.value }));
            }}
            placeholder="Paste auth middleware, domain rules, test helpers, or team conventions."
            value={formState.repoContext}
          />
        </div>

        <fieldset>
          <legend className="text-sm font-semibold text-slate-800">Focus areas</legend>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {allFocusAreas.map((focusArea) => {
              const checked = formState.focusAreas.includes(focusArea);
              return (
                <label
                  className={`flex cursor-pointer items-center justify-between rounded-2xl border px-4 py-3 text-sm transition ${checked ? "border-teal-300 bg-teal-50 text-teal-900" : "border-slate-200 bg-slate-50 text-slate-700"}`}
                  key={focusArea}
                >
                  <span className="font-medium capitalize">{focusArea}</span>
                  <input
                    checked={checked}
                    className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    onChange={() => {
                      toggleFocusArea(focusArea);
                    }}
                    type="checkbox"
                  />
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="space-y-2">
          <label className="block text-sm font-semibold text-slate-800" htmlFor="strictness">
            Strictness
          </label>
          <select
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-400 focus:bg-white"
            id="strictness"
            onChange={(event) => {
              setFormState((current) => ({
                ...current,
                strictness: event.target.value as ReviewStrictness,
              }));
            }}
            value={formState.strictness}
          >
            <option value="quiet">Quiet</option>
            <option value="balanced">Balanced</option>
            <option value="strict">Strict</option>
          </select>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={isLoading}
            type="submit"
          >
            {isLoading ? "Reviewing..." : "Review pull request"}
          </button>
          <button
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-teal-400 hover:text-teal-700"
            onClick={() => {
              setFormState({
                githubUrl: "https://github.com/example/example/pull/123",
                repoContext: sampleRepoContext,
                focusAreas: [...defaultFocusAreas],
                strictness: "balanced",
              });
              setUrlError(null);
              onReset();
            }}
            type="button"
          >
            Load sample
          </button>
          <button
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-950 hover:text-slate-950"
            onClick={() => {
              setFormState({
                githubUrl: "",
                repoContext: "",
                focusAreas: [...defaultFocusAreas],
                strictness: "balanced",
              });
              setUrlError(null);
              onReset();
            }}
            type="button"
          >
            Clear
          </button>
        </div>
      </form>
    </section>
  );
}

function isGitHubPullRequestUrl(value: string): boolean {
  return /^https:\/\/github\.com\/[^/]+\/[^/]+\/pull\/\d+\/?$/.test(value.trim());
}
