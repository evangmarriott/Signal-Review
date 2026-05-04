# Video Demo Script

A script for recording a short demo video of SignalReview. Target length: 3–5 minutes. Record with Loom or QuickTime.

---

## Setup Before Recording

- Backend running on port 8000
- Frontend running on port 5173
- Browser open to `http://localhost:5173`
- Terminal hidden or in a clean state
- No unrelated tabs visible

---

## Script

### [0:00–0:20] Hook

> "This is SignalReview — an AI pull request reviewer that filters its own output by severity and confidence, so developers only see the comments worth acting on."

Show the empty form on screen.

---

### [0:20–0:45] Load the sample

Click **Load sample**.

> "The form has three inputs: a GitHub PR URL, optional repo context, and a strictness setting. The repo context is where teams paste their auth middleware, team rules, or conventions — things Claude can't infer from the diff alone."

Point to the repo context field showing the auth middleware snippet and the team rule about object-level authorization.

---

### [0:45–1:15] Submit and show the result

Click **Review pull request**. Wait for the result to load.

> "The backend fetches the PR diff, sends it to Claude with the repo context baked into the prompt, validates the structured JSON with Pydantic, and applies the Signal Filter."

Point to the result:

> "Every review includes an overall risk level, a merge recommendation, and a plain-English summary. Comments are split into visible and hidden — the Signal Filter decided which is which."

---

### [1:15–2:00] Walk through a comment

Click to expand a comment card.

> "Each comment has to earn its place. It needs a title, a severity and confidence grade, the exact problem, why it matters, and a suggested fix. Vague warnings don't make it through."

Point to the severity and confidence badges.

> "In balanced mode, medium-severity comments only show if confidence is high. Low-severity comments are hidden by default but still accessible."

Expand the hidden comments section.

> "The hidden comments aren't deleted — they're just out of the way until the developer wants more detail."

---

### [2:00–2:30] Show the Signal Filter

Switch strictness to **Quiet** and resubmit.

> "Quiet mode shows only critical and high severity issues with high confidence — the things that should block a merge."

Switch to **Strict** and resubmit.

> "Strict mode opens up to medium-confidence issues. Same PR, same AI output — the filter decides what to surface."

---

### [2:30–3:30] GitHub App — inline threads

Switch to the browser tab showing the GitHub PR.

> "SignalReview also runs as a GitHub App. When a PR is opened, a webhook fires, and the review is posted back as inline threads anchored to the exact lines in the diff."

Scroll through the Files changed tab, showing inline threads.

> "The backend parses the unified diff to build a line map for every changed file, then anchors each comment to the right or left side of the diff."

Click the **Details** toggle on an inline thread.

> "The why-it-matters and suggested fix are collapsed by default so the thread doesn't dominate the diff view."

Click **Apply suggestion** on a thread that has a code suggestion.

> "For small, safe fixes, Claude includes a suggestion block that GitHub can apply directly as a commit."

---

### [3:30–4:00] Check Run

Go to the Checks tab on the PR.

> "SignalReview posts a check run on the head commit. Teams can require it to pass before merging."

Point to the check run status.

> "The check run title shows the risk level and merge recommendation. The details link goes to the full review output."

---

### [3:50–4:10] Close

> "The core idea is that AI review is only useful if developers trust it. SignalReview earns that trust by grading every comment and letting the Signal Filter do the triage — so the default view is always worth reading."

End on the PR review body showing the structured summary.

---

## After Recording

Add the video link to the README:

```md
## Demo

[Watch the demo](https://your-loom-link-here)
```
