# Demo Walkthrough

https://github.com/user-attachments/assets/51ca5346-d01f-4d85-87f3-999696ff1e6f

A step-by-step guide for demoing SignalReview. The demo has two parts: the frontend review flow (no credentials needed) and the GitHub App flow (requires a running backend and ngrok).

---

## Prerequisites

Start both services before demoing:

```bash
# Terminal 1 — backend
cd backend
uv run uvicorn src.main:app --reload --reload-exclude ".venv"

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:5173`.

---

## Part 1: Frontend Review Flow

This part works without any API keys — the sample URL always returns a realistic mock review.

### Step 1 — Load the sample

Click **Load sample**. This populates:
- A demo PR URL
- A repo context snippet showing the team's auth middleware and the object-level authorization rule
- Focus areas: security, logic, tests
- Strictness: balanced

**Talking point:** The repo context field is how teams feed SignalReview their domain rules — things Claude can't infer from the diff alone.

### Step 2 — Submit the review

Click **Review pull request**. The result loads in a few seconds.

**Talking point:** The backend fetches the PR diff, sends it to Claude with the repo context and focus areas baked into the prompt, validates the structured JSON output with Pydantic, and applies the Signal Filter before returning.

### Step 3 — Walk through the result

Point out:

- **Overall risk badge** — high risk, request changes
- **Summary** — one paragraph explaining the main issue
- **Visible comments** — each card shows severity, confidence, category, and location
- **Expand a comment** — click the details toggle to show why it matters and the suggested fix
- **Signal Filter summary** — explains how many comments are shown vs. hidden
- **Hidden comments** — expand the hidden section to show lower-signal findings are still accessible

**Talking point:** Every comment must justify itself. It has to say what the problem is, why it matters, and how to fix it. No vague warnings.

### Step 4 — Show the Signal Filter in action

Without resubmitting, explain what changes across modes. Then resubmit twice to show the difference:

| Mode | Visible | Hidden | What changes |
|------|---------|--------|--------------|
| Quiet | 1 | 3 | Only critical/high issues with high confidence |
| Balanced | 2 | 2 | Adds medium severity issues with high confidence |
| Strict | 3 | 1 | Also surfaces medium-confidence issues |

**Talking point:** The Signal Filter is the core product differentiator. Most AI review tools show everything — SignalReview ranks it. Developers can trust the default view because the noise is hidden, not deleted.

### Step 5 — Show file summaries

Scroll to the file summaries section at the bottom of the result.

**Talking point:** Each changed file gets a one-line risk assessment. Useful for quickly understanding what a large PR is actually touching.

---

## Part 2: GitHub App Flow

This part requires the backend running, ngrok tunnelling to port 8000, and the GitHub App configured.

### Setup

```bash
# Terminal 3 — tunnel
ngrok http 8000
```

Make sure the GitHub App webhook URL in GitHub settings points to the current ngrok URL at `/api/github/webhooks`.

### Step 1 — Open a test PR

Create a branch with a deliberate security issue and open a PR against main. The app triggers automatically on `opened`, `reopened`, and `synchronize` events.

### Step 2 — Show the Check Run

Go to the PR → **Checks** tab. SignalReview appears as an in-progress check while the review runs, then updates to success or failure when done.

**Talking point:** The check run blocks merge on critical findings. Teams can configure branch protection to require it to pass.

### Step 3 — Show inline review threads

Go to **Files changed**. Each comment is anchored to the exact line in the diff.

Point out the inline thread structure:
- Title and severity visible immediately
- **Details** toggle collapses why it matters and the suggested fix
- **Apply suggestion** button lets reviewers commit the fix directly from GitHub

**Talking point:** The diff line anchoring is non-trivial. The backend parses unified diff hunks to build a line map, then anchors each comment to the RIGHT or LEFT side of the diff. Comments that can't be anchored fall back gracefully to the review body.

### Step 4 — Show the review body comment

Scroll up to the PR conversation. SignalReview posts a structured review body with:
- Risk and merge recommendation header
- Review overview counts
- Key findings list with severity labels
- Collapsible sections for summary-only findings, hidden comments, and file summaries

**Talking point:** The PR comment is the fallback path. If inline threads fail for any reason, the full review still lands as a top-level comment. If that also fails, the backend logs the PR URL so the result is never silently lost.

---

## Key Talking Points

**Why not just show everything?**
AI reviewers that show 20 comments per PR train developers to ignore them. SignalReview forces a severity and confidence grade on every comment, then uses that metadata to decide what to show. The default view earns trust because it's curated.

**Why the repair loop?**
Claude occasionally returns JSON that passes syntax checks but fails schema validation — a missing field, a wrong enum value. Rather than erroring, the backend sends the bad response back with the validation error and asks for a corrected version. This makes the structured output reliable without requiring a perfect prompt.

**Why a GitHub App instead of just a webhook?**
The GitHub App uses installation tokens scoped to the repository. It can post inline review threads, create check runs, and integrate with branch protection. A plain webhook can only read events — it can't write back to GitHub.

**What's next for production?**
- Persist installation state and review runs in a database
- Auto-fetch repo context: README, team rules, related tests, package files
- Deduplicate and update prior comments on synchronize events
- Track acceptance rate per comment type to learn what counts as noise
