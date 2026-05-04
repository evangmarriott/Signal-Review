# Build Prompts

These are the prompts used to build SignalReview with AI assistance.

---

## 1. Project Scaffolding

```
scaffold a new project called SignalReview. it should have two parts: a Python FastAPI backend and a React TypeScript frontend.

for the backend:
- use uv for dependency management with a pyproject.toml
- set up strict mypy (strict = true, no implicit optionals, warn unused ignores)
- configure ruff for linting with E, F, I, B, UP rules
- dependencies: fastapi, uvicorn, httpx, pydantic, pydantic-settings, anthropic
- dev dependencies: pytest, pytest-asyncio, mypy, ruff
- the app factory should live in src/main.py and wire up CORS middleware, exception handlers, and routers
- CORS should read allowed origins from a CORS_ORIGINS env var, support comma-separated values, and strip trailing slashes
- settings should use pydantic-settings with an lru_cache getter, reading from a .env file
- settings fields: ANTHROPIC_API_KEY, GITHUB_TOKEN, ENVIRONMENT, APP_VERSION, CORS_ORIGINS

for the frontend:
- use vite + react + typescript
- install tailwind v4, axios, @tanstack/react-query
- strict tsconfig: strict, noUnusedLocals, noUnusedParameters, noFallthroughCasesInSwitch
- configure the @/* path alias pointing to ./src/*
- create a basic App.tsx shell

also create:
- a root .gitignore that excludes .env, .env.local, .venv, __pycache__, dist, node_modules, and backend/secret-key.pem
- a backend/.env.example with placeholder values for all settings
- a frontend/.env.example with VITE_API_BASE_URL=http://localhost:8000
```

---

## 2. Custom Exceptions and Error Handling

```
add a custom exception hierarchy to the backend. create backend/src/exceptions/custom.py with a base SignalReviewError class and these subtypes:

- InvalidGitHubURLError (400) — raised when the PR URL doesn't match the expected GitHub pull request format
- GitHubAPIError (502) — raised when the GitHub API returns an error or unexpected response
- ReviewerAPIError (502) — raised when the Anthropic API call fails or returns malformed output
- GitHubAppConfigurationError (500) — raised when required GitHub App env vars are missing
- GitHubWebhookSignatureError (401) — raised when the HMAC webhook signature doesn't match
- GitHubWebhookPayloadError (422) — raised when the webhook JSON is missing required fields

then create backend/src/exceptions/handlers.py that registers FastAPI exception handlers for each type. all error responses should use a consistent shape: { "error": <slug>, "detail": <message>, "status_code": <int> }. also register a handler for RequestValidationError that returns the same shape with error "validation_error".
```

---

## 3. Request and Response Models

```
create the pydantic models for the review API.

backend/src/models/requests.py:
- ReviewFocus enum: security, logic, performance, tests, style
- ReviewStrictness enum: quiet, balanced, strict
- PRReviewRequest model with:
  - github_url: str — must match https://github.com/{owner}/{repo}/pull/{number} exactly, raise InvalidGitHubURLError if not
  - repo_context: str | None
  - focus_areas: list[ReviewFocus] defaulting to [security, logic, tests]
  - strictness: ReviewStrictness defaulting to balanced

backend/src/models/responses.py:
- ReviewSeverity enum: critical, high, medium, low
- ReviewConfidence enum: high, medium, low
- ReviewCategory enum: security, logic, performance, tests, style
- OverallRisk enum: critical, high, medium, low
- MergeRecommendation enum: request_changes, comment, approve
- ReviewComment model: title, file (optional), line (optional), category, severity, confidence, problem, why_it_matters, suggestion, code_suggestion (optional), is_hidden_by_default (default False)
- FileSummary model: filename, change_type, risk_level (OverallRisk), summary
- PRReviewResult model: pr_title, pr_author, pr_url, overall_risk, merge_recommendation, summary, visible_comments, hidden_comments, total_comments, visible_comments_count, hidden_comments_count, signal_filter_summary, file_summaries
- RawAIReviewResult model (for validating Claude output before signal filtering): overall_risk, merge_recommendation, summary, comments, file_summaries
```

---

## 4. GitHub Service

```
create backend/src/services/github.py to fetch PR data from the GitHub API.

implement:
- ParsedPullRequest dataclass: owner, repo, pull_number
- GitHubChangedFile pydantic model: filename, status, additions, deletions, changes, patch (optional)
- GitHubPRMetadata pydantic model: title, author, html_url, body, base_branch, head_branch
- parse_pr_url(url: str) -> ParsedPullRequest — parse and validate a GitHub PR URL, raise InvalidGitHubURLError for anything that doesn't match
- build_github_headers() -> dict — returns Accept and User-Agent headers, adds Authorization header if GITHUB_TOKEN is set in settings
- fetch_pr_metadata(owner, repo, pull_number) -> GitHubPRMetadata — calls GET /repos/{owner}/{repo}/pulls/{pull_number}
- fetch_pr_files(owner, repo, pull_number) -> list[GitHubChangedFile] — calls GET /repos/{owner}/{repo}/pulls/{pull_number}/files
- build_combined_diff(files) -> str — formats all changed files into a single readable diff string. for each file include a header with filename and status, then the patch if available, or a note that no text patch is available for binary/large files

for the demo URL https://github.com/example/example/pull/123 return hardcoded mock metadata and files so the app is always demoable without a real GitHub token.
```

---

## 5. Reviewer Service

```
create backend/src/services/reviewer.py to call Anthropic Claude and return a structured review.

the SYSTEM_PROMPT should instruct the model to:
- act as a senior engineer giving high-signal code review comments only
- only report issues grounded in the diff or supplied repo context — no speculative issues
- require every comment to have: title, file, line, category, severity (critical/high/medium/low), confidence (high/medium/low), problem, why_it_matters, suggestion, and optionally code_suggestion
- produce a single-line code_suggestion only when the fix is a small, safe, self-contained change that fits within the changed lines — leave it null otherwise
- include an overall_risk, merge_recommendation (request_changes/comment/approve), summary, and file_summaries
- Return JSON only — no markdown wrapper, no prose before or after

also create a REPAIR_SYSTEM_PROMPT used in a second-pass repair call when the first response fails Pydantic validation. it should instruct the model to fix the JSON to match the required schema, Return JSON only.

implement analyze_pr(metadata, combined_diff, repo_context, focus_areas) -> PRReviewResult:
- build a user message that includes the PR title, author, branch info, optional repo context, focus areas, and the combined diff
- call claude-sonnet-4-20250514 with a 4096 max_tokens limit
- validate the response with the RawAIReviewResult pydantic model
- if validation fails, make a second repair call using REPAIR_SYSTEM_PROMPT with the original prompt, bad response, and validation error
- if the repair also fails, raise ReviewerAPIError
- if ANTHROPIC_API_KEY is missing OR the URL is the demo URL, return a realistic hardcoded mock review that demonstrates the signal filter (include a mix of severities and confidences so the filtering behavior is visible)
```

---

## 6. Signal Filter

```
create backend/src/services/signal_filter.py.

implement apply_signal_filter(comments, strictness) -> tuple[list[ReviewComment], list[ReviewComment]]:
- returns (visible_comments, hidden_comments)
- sets is_hidden_by_default=False on visible, True on hidden
- filtering rules:
  - quiet: show only critical or high severity AND high confidence
  - balanced: hide anything with low confidence or low severity; medium severity requires high confidence; high/critical requires at least medium confidence
  - strict: show critical/high/medium with at least medium confidence; show low severity only if high confidence

implement build_signal_filter_summary(visible, hidden, strictness) -> str:
- returns a one-line human-readable summary like "Balanced mode showed 3 high-signal comments and hid 2 lower-confidence or lower-severity comments."
- handle singular/plural correctly
```

---

## 7. Review Flow Orchestrator

```
create backend/src/services/review_flow.py with a single function perform_pr_review that orchestrates the full review pipeline:

perform_pr_review(owner, repo, pull_number, repo_context, focus_areas, strictness, github_token=None) -> PRReviewResult:
1. fetch PR metadata using fetch_pr_metadata
2. fetch changed files using fetch_pr_files
3. build the combined diff string
4. call analyze_pr to get the raw AI review
5. apply the signal filter to split visible and hidden comments
6. build the signal filter summary string
7. return a PRReviewResult with all fields populated including pr_title, pr_author, pr_url, visible_comments, hidden_comments, total_comments, visible_comments_count, hidden_comments_count, signal_filter_summary, file_summaries
```

---

## 8. Review API Router

```
create backend/src/routers/review.py with two endpoints:

GET /api/health:
- returns { "status": "ok", "version": <APP_VERSION from settings> }

POST /api/review:
- accepts a PRReviewRequest body
- parses the GitHub PR URL with parse_pr_url
- calls perform_pr_review with the parsed owner/repo/pull_number and request fields
- returns the full PRReviewResult

wire both routers into the FastAPI app in src/main.py with an /api prefix.
```

---

## 9. React Frontend

```
build the React TypeScript frontend for SignalReview.

types/review.ts — mirror all backend response types:
- enums for ReviewSeverity, ReviewConfidence, ReviewCategory, OverallRisk, MergeRecommendation
- interfaces for ReviewComment, FileSummary, PRReviewResult, ErrorResponse

api/client.ts:
- create an axios instance with baseURL from VITE_API_BASE_URL env var, timeout 60000, Content-Type application/json
- export postJson<TResponse>(path, payload) that throws a typed APIClientError on failure
- APIClientError should carry the error slug, message, and status code from the backend ErrorResponse shape

api/review.ts:
- export submitReview(request) that posts to /api/review and returns PRReviewResult

hooks/useReview.ts:
- use TanStack Query useMutation to call submitReview
- expose { submitReview, result, isLoading, error, reset }

components/ReviewForm.tsx:
- controlled form with fields: GitHub PR URL, optional repo context textarea, focus area checkboxes (security/logic/performance/tests/style), strictness radio buttons (quiet/balanced/strict)
- validate the URL client-side before submitting — must match https://github.com/{owner}/{repo}/pull/{number}
- include a "Load sample" button that populates a demo PR URL, sample repo context, and default focus areas so the app is immediately demoable
- disable the submit button while loading

components/SummaryCard.tsx:
- shows pr_title, pr_author, overall_risk badge, merge_recommendation badge, summary text, visible/hidden comment counts, and signal_filter_summary
- color-code the risk and recommendation badges

components/IssueCard.tsx:
- renders a single ReviewComment
- shows title, severity badge, confidence badge, category badge, file+line location
- collapsible sections for problem, why it matters, and suggestion
- hidden comments should be visually de-emphasised

components/ReviewResult.tsx:
- renders SummaryCard
- renders visible IssueCard list
- if hidden_comments_count > 0, renders a collapsible section to reveal hidden IssueCard list
- renders file summaries section

App.tsx:
- manages form/loading/result/error state
- renders ReviewForm, loading spinner, ReviewResult, or error message depending on state
```

---

## 10. GitHub App — Auth and Webhooks

```
create backend/src/services/github_app.py to handle GitHub App authentication and webhook processing.

add new settings fields: GITHUB_APP_ID, GITHUB_WEBHOOK_SECRET, GITHUB_PRIVATE_KEY, GITHUB_CHECK_RUN_NAME (default "SignalReview"). GITHUB_PRIVATE_KEY should accept either a PEM block with literal newlines or a single-line string with \n escapes — normalise to a real PEM on load.

implement:

verify_webhook_signature(body: bytes, signature_header: str | None):
- compute HMAC-SHA256 of body using GITHUB_WEBHOOK_SECRET
- compare with the X-Hub-Signature-256 header using hmac.compare_digest
- raise GitHubWebhookSignatureError if missing or mismatched

build_github_app_jwt() -> str:
- mint a JWT signed with the app's RS256 private key
- iat = now - 60s (clock skew buffer), exp = now + 9 minutes, iss = GITHUB_APP_ID

request_installation_token(installation_id) -> str:
- POST to /app/installations/{installation_id}/access_tokens with the app JWT
- return the token string from the response

parse_pull_request_webhook(payload) -> PullRequestWebhookContext | None:
- extract action, installation_id, owner, repo, pull_number, head_sha, pr_url
- return None for actions other than opened/reopened/synchronize
- raise GitHubWebhookPayloadError for missing required fields

handle_pull_request_webhook(context: PullRequestWebhookContext):
- get an installation token
- create a "in_progress" check run on the head SHA
- run perform_pr_review with the installation token
- publish the result back to GitHub
- update the check run to completed/success or failure

create backend/src/routers/github_webhooks.py:
- POST /api/github/webhooks
- read raw body, verify signature
- parse payload, call parse_pull_request_webhook
- if a PR context is returned, dispatch handle_pull_request_webhook as a FastAPI BackgroundTask
- always return 200 immediately so GitHub doesn't retry
```

---

## 11. GitHub App — Check Runs and PR Reviews

```
extend github_app.py with GitHub Check Run and Pull Request Review publishing.

implement create_check_run(owner, repo, head_sha, installation_token, status, conclusion, output):
- POST to /repos/{owner}/{repo}/check-runs
- on "in_progress": no conclusion, minimal output
- on "completed": include conclusion (success/failure/neutral) and a structured output with title and summary

implement _build_structured_review_draft(result, changed_files) -> StructuredReviewDraft:
- parse the diff patches for all changed files to build a map of filename -> (right_line_set, left_line_set)
- for each visible comment that has a file and line, check if the line exists in the diff line sets and anchor it to RIGHT or LEFT side
- comments that can't be anchored fall back to the summary body as summary-only findings
- the review body (a markdown string) should include:
  - overall risk and merge recommendation header
  - review overview counts (inline threads, summary-only findings, hidden comments)
  - key findings list with severity labels
  - summary-only findings in a collapsible <details> block
  - hidden comments in a collapsible <details> block
  - file summaries in a collapsible <details> block

implement create_pull_request_review(owner, repo, pull_number, head_sha, installation_token, draft):
- POST to /repos/{owner}/{repo}/pulls/{pull_number}/reviews
- include the body, event (COMMENT or REQUEST_CHANGES), and inline thread comments
- each inline thread: path, line, side, body
- the inline thread body should show title + severity + problem upfront, with why_it_matters and suggested fix collapsed in a <details> block, and the code suggestion block (```suggestion```) outside the details so the GitHub Apply button works

implement try_publish_pull_request_review with a fallback chain:
1. try create_pull_request_review with inline threads
2. if that fails, try posting a plain PR comment with create_pr_review_comment
3. if that also fails, log the PR URL so the result isn't lost entirely

the PR comment fallback (_build_pr_review_comment_body) should render each visible comment in a <details> collapsible block and hidden comments in a second collapsible block.
```

---

## 12. Tests

```
add a comprehensive test suite to the backend.

backend/tests/conftest.py:
- pytest fixture that creates a FastAPI TestClient with ANTHROPIC_API_KEY unset and all GitHub App vars unset, so tests run without real credentials

backend/tests/unit/test_github.py:
- test parse_pr_url returns correct owner, repo, pull_number for a valid URL
- test parse_pr_url raises InvalidGitHubURLError for a GitLab URL
- test parse_pr_url raises InvalidGitHubURLError for an issues URL (not a pull)
- test build_combined_diff includes filename, status, and patch content
- test build_combined_diff handles files with no patch (binary/large)

backend/tests/unit/test_reviewer.py:
- test that analyze_pr returns the mock review when ANTHROPIC_API_KEY is missing
- test SYSTEM_PROMPT and REPAIR_SYSTEM_PROMPT contain required instructions
- test that malformed JSON from the API raises ReviewerAPIError (mock AsyncAnthropic)
- test that a schema mismatch triggers a repair call and the repaired result is returned (mock AsyncAnthropic to return bad JSON on first call, valid JSON on second)

backend/tests/unit/test_signal_filter.py:
- test quiet mode: only critical/high + high confidence are visible
- test balanced mode: hides low severity and low confidence
- test strict mode: shows medium and high, hides only low severity + low confidence
- test visible comments get is_hidden_by_default=False
- test hidden comments get is_hidden_by_default=True
- test build_signal_filter_summary produces the correct string with singular/plural handling

backend/tests/unit/test_github_app.py:
- test _build_pr_review_comment_body contains all expected sections
- test _build_structured_review_draft creates inline threads for comments anchored in the diff
- test _build_structured_review_draft falls back to summary-only for comments with no diff anchor
- test _build_structured_review_draft handles missing patches
- test _build_github_suggestion_block formats the suggestion fence correctly
- test _build_github_suggestion_block returns None for blank suggestions
- test _build_diff_line_sets skips malformed patches with a warning
- test verify_webhook_signature passes for a valid HMAC
- test verify_webhook_signature raises GitHubWebhookSignatureError for a bad signature
- test parse_pull_request_webhook returns None for non-PR actions (e.g. labeled)
- test parse_pull_request_webhook raises GitHubWebhookPayloadError for missing fields
- test handle_pull_request_webhook calls try_publish_pull_request_review (mock httpx)
- test GITHUB_APP_REVIEWER_CONTEXT string is non-empty

backend/tests/integration/test_review_router.py:
- test GET /api/health returns { status: ok, version }
- test POST /api/review with an invalid URL returns 422 with error: validation_error
- test POST /api/review with a valid request returns 200 with correct PRReviewResult shape (mock perform_pr_review and parse_pr_url)

backend/tests/integration/test_github_webhooks_router.py:
- test POST /api/github/webhooks with a missing signature returns 401
- test POST /api/github/webhooks with a bad signature returns 401
- test POST /api/github/webhooks with a non-PR event (push) returns 200 and does nothing
- test POST /api/github/webhooks with a valid PR opened event returns 200 and dispatches the handler as a background task (mock handle_pull_request_webhook)
```

---

## 13. GitHub Actions CI

```
add GitHub Actions CI for both backend and frontend.

.github/workflows/backend-ci.yml:
- trigger on push and pull_request to main
- runs on ubuntu-latest
- steps: checkout, install uv, install dependencies with uv sync --extra dev, run ruff check, run mypy, run pytest

.github/workflows/frontend-ci.yml:
- trigger on push and pull_request to main
- runs on ubuntu-latest
- steps: checkout, setup node 20, npm install, run eslint, run tsc --noEmit (typecheck), run npm run build
```

---

## 14. README

```
write a comprehensive README.md for SignalReview covering:

- what the product does and the core insight (optimizing for trust over coverage)
- architecture overview (backend flow numbered 1-7, frontend summary)
- MVP scope: what's included and what's intentionally out of scope
- full repository structure tree
- backend setup: prerequisites, install and run commands, all env vars with descriptions
- frontend setup: prerequisites, install and run commands, env vars
- running locally (both services)
- tests and checks: all commands for ruff, mypy, pytest, eslint, typecheck, build
- API endpoint documentation: GET /api/health, POST /api/review (request and response fields), POST /api/github/webhooks
- GitHub App setup: required permissions (Checks read/write, Contents read, Pull requests read/write), webhook events, env var configuration, ngrok for local development
- demo mode explanation: what the sample loader populates and what the backend mock returns
- why severity/confidence filtering matters (the product differentiator)
- production roadmap (7 items: persistence, automatic repo context, embeddings, inline comments, deduplication, feedback learning, dashboarding)
```
