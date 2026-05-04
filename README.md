# SignalReview

SignalReview is a low-noise AI pull request reviewer. Instead of flooding a PR with every possible suggestion, it ranks comments by severity and confidence, hides lower-signal comments by default, and requires every issue to explain why it matters and how to fix it. The MVP fetches public GitHub PR diffs by URL and supports optional pasted repo context. In production, this would become a GitHub App that automatically fetches broader repo context and posts selected high-confidence comments back to the PR.

## Product Insight

Most AI PR review tools optimize for coverage, which often creates too much noise. SignalReview optimizes for trust:

- Every comment must include severity, confidence, category, problem, why it matters, and a suggested fix.
- A Signal Filter separates visible high-signal comments from hidden low-signal comments.
- Developers can expand hidden comments when they want more breadth, but the default view stays concise.

## Architecture

SignalReview is a simple two-part MVP:

- `backend/`: FastAPI service that fetches GitHub PR metadata and diffs, calls Anthropic Claude, validates the response with Pydantic, and applies the Signal Filter.
- `frontend/`: React + TypeScript single-page app that submits a review request and renders visible comments, hidden comments, and file summaries.

Backend flow:

1. Validate the GitHub PR URL.
2. Fetch PR metadata and changed files from the public GitHub API.
3. Build a combined diff string.
4. Send diff + optional repo context + selected focus areas to Claude.
5. Validate structured JSON with Pydantic.
6. Apply Signal Filter based on `quiet`, `balanced`, or `strict`.
7. Return a typed `PRReviewResult`.

## MVP Scope

Included:

- Public GitHub PR URL review
- GitHub PR diff fetching
- GitHub App webhook intake for pull request events
- GitHub Check Run publishing for GitHub App-triggered reviews
- Inline PR review threads with diff-anchored comments
- Fallback PR comment when inline thread anchoring is not possible
- Optional manual repo context
- Anthropic Claude integration
- Mock demo fallback when `ANTHROPIC_API_KEY` is missing
- Strict Pydantic validation of AI output
- Signal Filter severity/confidence filtering
- FastAPI backend
- React + TypeScript frontend
- Backend unit and integration tests
- Basic GitHub Actions CI

Intentionally out of scope:

- GitHub OAuth
- Database-backed GitHub App installation management
- Database or accounts
- Full repo indexing
- Complex deployment automation

## Repository Structure

```text
backend/
  src/
    config.py
    main.py
    routers/
      review.py
      github_webhooks.py
    services/
      github.py
      github_app.py
      review_flow.py
      reviewer.py
      signal_filter.py
    models/
      requests.py
      responses.py
    exceptions/
      custom.py
      handlers.py
  tests/
    conftest.py
    unit/
    integration/
frontend/
  src/
    api/
    hooks/
    components/
    types/
.github/workflows/
README.md
```

## Backend Setup

Prerequisites:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

Install and run:

```bash
cd backend
cp .env.example .env
uv sync --extra dev
uv run uvicorn src.main:app --reload
```

Backend environment variables in `backend/.env`:

```env
ANTHROPIC_API_KEY=
GITHUB_TOKEN=
GITHUB_APP_ID=
GITHUB_WEBHOOK_SECRET=
GITHUB_PRIVATE_KEY=
GITHUB_CHECK_RUN_NAME=SignalReview
ENVIRONMENT=development
APP_VERSION=0.1.0
CORS_ORIGINS=http://localhost:5173
```

Notes:

- `GITHUB_TOKEN` is optional. If present, it is used for GitHub API requests to improve rate limits.
- `GITHUB_APP_ID`, `GITHUB_WEBHOOK_SECRET`, and `GITHUB_PRIVATE_KEY` are required for GitHub App webhook processing.
- `GITHUB_PRIVATE_KEY` can be pasted as a PEM block or as a single line with `\n` escapes.
- If `ANTHROPIC_API_KEY` is missing, SignalReview uses a realistic mock review so the app remains demoable.
- The sample URL `https://github.com/example/example/pull/123` is always served from a backend mock path.

## Frontend Setup

Prerequisites:

- Node.js 20+

Install and run:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Frontend environment variables in `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Running Locally

Start backend:

```bash
cd backend
uv run uvicorn src.main:app --reload
```

Start frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Then open the Vite URL, usually `http://localhost:5173`.

## Tests And Checks

Backend:

```bash
cd backend
uv run ruff check src tests main.py
uv run mypy src tests main.py --config-file mypy.ini
uv run pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## API Endpoints

`GET /api/health`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

`POST /api/review`

Request fields:

- `github_url`
- `repo_context`
- `focus_areas`
- `strictness`

Response fields include:

- PR metadata
- overall risk
- merge recommendation
- summary
- visible comments
- hidden comments
- visible/hidden counts
- Signal Filter summary
- per-file summaries

`POST /api/github/webhooks`

- Verifies the `X-Hub-Signature-256` signature from GitHub.
- Accepts `pull_request` events for `opened`, `reopened`, and `synchronize`.
- Runs the existing review pipeline with a GitHub App installation token.
- Publishes the result back to GitHub as a Check Run on the PR head SHA.

## GitHub App Setup

Create a GitHub App with:

- Webhook URL: `https://your-domain.example/api/github/webhooks`
- Webhook secret: set the same value in `GITHUB_WEBHOOK_SECRET`
- Repository permissions:
  - `Checks: Read and write`
  - `Contents: Read-only`
  - `Pull requests: Read and write`
- Subscribe to events:
  - `Pull request`

Then set in `backend/.env`:

```env
GITHUB_APP_ID=1234567
GITHUB_WEBHOOK_SECRET=replace-me
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_CHECK_RUN_NAME=SignalReview
```

For local development, expose the backend with a tunnel such as `ngrok` and use the tunneled `/api/github/webhooks` URL in the GitHub App settings.

## Demo Mode

The frontend includes a sample loader that populates:

- `https://github.com/example/example/pull/123`
- Auth middleware context
- A team rule about object-level authorization

The backend recognizes that URL and returns a deterministic mock review. In balanced mode, the low-severity DTO comment is hidden by default, which makes the Signal Filter behavior easy to demo.

## Why Severity/Confidence Filtering Matters

AI review comments are only useful when developers trust them. SignalReview forces the model to grade each issue, then turns that metadata into product behavior:

- Quiet mode shows only severe, high-confidence issues.
- Balanced mode shows likely-important issues without burying the user in speculative feedback.
- Strict mode broadens visibility while still suppressing the weakest comments.

This makes the product clearly different from a generic AI reviewer: the core feature is not just comment generation, it is comment triage.

## Production Roadmap

1. Persist GitHub App installations, review runs, and posted comment IDs.
2. Fetch changed files, related tests, README files, package files, and team rules automatically.
3. Retrieve broader repo context with embeddings or repository indexing.
4. Post selected inline comments back to GitHub.
5. Deduplicate and update prior comments across synchronize events.
6. Let teams accept or reject AI comments to learn what counts as noise.
7. Add dashboarding for acceptance rate, hidden-comment rate, and false positive rate.
