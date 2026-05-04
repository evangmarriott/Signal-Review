"""GitHub App authentication, webhook, and Check Run helpers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from src.config import get_settings
from src.exceptions.custom import (
    GitHubAPIError,
    GitHubAppConfigurationError,
    GitHubWebhookPayloadError,
    GitHubWebhookSignatureError,
    ReviewerAPIError,
)
from src.models.requests import ReviewFocus, ReviewStrictness
from src.models.responses import MergeRecommendation, PRReviewResult, ReviewComment
from src.services.github import (
    GITHUB_API_BASE_URL,
    GitHubChangedFile,
    build_github_headers,
    fetch_pr_files,
)
from src.services.review_flow import perform_pr_review

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_APP_FOCUS_AREAS = [
    ReviewFocus.SECURITY,
    ReviewFocus.LOGIC,
    ReviewFocus.TESTS,
]
DEFAULT_GITHUB_APP_STRICTNESS = ReviewStrictness.BALANCED
GITHUB_APP_REVIEWER_CONTEXT = """
Repository context for this review:
- `backend/src/services/github_app.py` contains internal helpers invoked only from the verified
  GitHub webhook flow.
- `installation_token` values are minted by GitHub for this app installation and are not
  user-supplied input.
- `owner`, `repo`, `pull_number`, PR URLs, and similar GitHub metadata are not secrets.
- `PRReviewResult` objects are internal typed model output, not raw user input from an external
  request.
- Do not suggest extra authentication, token validation, or input sanitization for these internal
  values unless the diff clearly exposes them to an external caller.
- Logging repository identifiers alone is not a security issue.
- Missing tests are only worth flagging when changed behavior in the diff lacks visible coverage in
  the same diff.
""".strip()


@dataclass(frozen=True)
class PullRequestWebhookContext:
    action: str
    installation_id: int
    owner: str
    repo: str
    pull_number: int
    head_sha: str
    pr_url: str


@dataclass(frozen=True)
class StructuredReviewThread:
    path: str
    line: int
    side: str
    body: str


@dataclass(frozen=True)
class StructuredReviewDraft:
    body: str
    event: str
    inline_threads: list[StructuredReviewThread]


_DIFF_HUNK_HEADER_PATTERN = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")


def verify_webhook_signature(*, body: bytes, signature_header: str | None) -> None:
    """Verify the GitHub webhook signature header."""

    settings = get_settings()
    if settings.github_webhook_secret is None:
        raise GitHubAppConfigurationError("GITHUB_WEBHOOK_SECRET is required for webhooks.")
    if signature_header is None:
        raise GitHubWebhookSignatureError("Missing X-Hub-Signature-256 header.")
    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        raise GitHubWebhookSignatureError("Invalid X-Hub-Signature-256 header format.")

    expected_digest = hmac.new(
        settings.github_webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    provided_digest = signature_header.removeprefix(expected_prefix)
    if not hmac.compare_digest(expected_digest, provided_digest):
        raise GitHubWebhookSignatureError("GitHub webhook signature verification failed.")


def build_github_app_jwt() -> str:
    """Create a signed GitHub App JWT."""

    settings = get_settings()
    if settings.github_app_id is None:
        raise GitHubAppConfigurationError("GITHUB_APP_ID is required for GitHub App auth.")
    if settings.github_private_key is None:
        raise GitHubAppConfigurationError("GITHUB_PRIVATE_KEY is required for GitHub App auth.")

    try:
        import jwt
    except ImportError as exc:
        raise GitHubAppConfigurationError(
            "PyJWT is required for GitHub App auth. Run `uv sync --extra dev` in backend/."
        ) from exc

    now = datetime.now(UTC)
    payload = {
        "iat": int((now - timedelta(seconds=60)).timestamp()),
        "exp": int((now + timedelta(minutes=9)).timestamp()),
        "iss": settings.github_app_id,
    }
    token = jwt.encode(payload, settings.github_private_key, algorithm="RS256")
    return str(token)


async def request_installation_token(*, installation_id: int) -> str:
    """Exchange the GitHub App JWT for an installation token."""

    url = f"{GITHUB_API_BASE_URL}/app/installations/{installation_id}/access_tokens"
    headers = build_github_headers()
    headers["Authorization"] = f"Bearer {build_github_app_jwt()}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers)

    payload = _parse_json_response(response, resource_name="installation token")
    if not isinstance(payload, dict):
        raise GitHubAPIError("GitHub returned an unexpected installation token payload.")
    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise GitHubAPIError("GitHub installation token response did not include a token.")
    return token


def parse_pull_request_webhook(payload: object) -> PullRequestWebhookContext | None:
    """Extract the fields needed to review a pull request from a webhook payload."""

    if not isinstance(payload, dict):
        raise GitHubWebhookPayloadError("GitHub webhook payload must be a JSON object.")

    action = _read_required_str(payload, "action", "Webhook payload is missing action.")
    if action not in {"opened", "reopened", "synchronize"}:
        return None

    installation = _read_required_dict(
        payload,
        "installation",
        "Webhook payload is missing installation details.",
    )
    repository = _read_required_dict(
        payload,
        "repository",
        "Webhook payload is missing repository details.",
    )
    pull_request = _read_required_dict(
        payload,
        "pull_request",
        "Webhook payload is missing pull request details.",
    )
    owner_payload = _read_required_dict(
        repository,
        "owner",
        "Webhook payload is missing repository owner details.",
    )
    head_payload = _read_required_dict(
        pull_request,
        "head",
        "Webhook payload is missing pull request head details.",
    )

    installation_id = _read_required_int(
        installation,
        "id",
        "Webhook payload is missing installation ID.",
    )
    owner = _read_required_str(
        owner_payload,
        "login",
        "Webhook payload is missing repository owner login.",
    )
    repo = _read_required_str(
        repository,
        "name",
        "Webhook payload is missing repository name.",
    )
    pull_number = _read_required_int(
        pull_request,
        "number",
        "Webhook payload is missing pull request number.",
    )
    head_sha = _read_required_str(
        head_payload,
        "sha",
        "Webhook payload is missing pull request head SHA.",
    )
    pr_url = _read_required_str(
        pull_request,
        "html_url",
        "Webhook payload is missing pull request URL.",
    )

    return PullRequestWebhookContext(
        action=action,
        installation_id=installation_id,
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        head_sha=head_sha,
        pr_url=pr_url,
    )


async def handle_pull_request_webhook(context: PullRequestWebhookContext) -> None:
    """Review the PR and publish the result as a GitHub Check Run."""

    check_run_name = get_settings().github_check_run_name
    try:
        installation_token = await request_installation_token(
            installation_id=context.installation_id
        )
    except (GitHubAPIError, GitHubAppConfigurationError, httpx.HTTPError):
        logger.exception(
            "GitHub App auth failed for %s/%s#%s",
            context.owner,
            context.repo,
            context.pull_number,
        )
        return

    try:
        review_result = await perform_pr_review(
            owner=context.owner,
            repo=context.repo,
            pull_number=context.pull_number,
            repo_context=GITHUB_APP_REVIEWER_CONTEXT,
            focus_areas=DEFAULT_GITHUB_APP_FOCUS_AREAS,
            strictness=DEFAULT_GITHUB_APP_STRICTNESS,
            github_token=installation_token,
        )
    except (GitHubAPIError, ReviewerAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "GitHub App review failed for %s/%s#%s",
            context.owner,
            context.repo,
            context.pull_number,
        )
        await create_check_run(
            installation_token=installation_token,
            owner=context.owner,
            repo=context.repo,
            head_sha=context.head_sha,
            name=check_run_name,
            result=None,
            error_message=str(exc),
            external_id=f"pr-{context.pull_number}",
            details_url=context.pr_url,
        )
        return

    try:
        changed_files = await fetch_pr_files(
            owner=context.owner,
            repo=context.repo,
            pull_number=context.pull_number,
            github_token=installation_token,
        )
    except (GitHubAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "GitHub App failed to fetch PR files for %s/%s#%s",
            context.owner,
            context.repo,
            context.pull_number,
        )
        await create_check_run(
            installation_token=installation_token,
            owner=context.owner,
            repo=context.repo,
            head_sha=context.head_sha,
            name=check_run_name,
            result=None,
            error_message=f"GitHub PR file fetch failed: {exc}",
            external_id=f"pr-{context.pull_number}",
            details_url=context.pr_url,
        )
        return

    details_url = context.pr_url
    try:
        posted_comment_url = await try_publish_pull_request_review(
            installation_token=installation_token,
            owner=context.owner,
            repo=context.repo,
            pull_number=context.pull_number,
            head_sha=context.head_sha,
            changed_files=changed_files,
            result=review_result,
        )
        if posted_comment_url is not None:
            details_url = posted_comment_url

        await create_check_run(
            installation_token=installation_token,
            owner=context.owner,
            repo=context.repo,
            head_sha=context.head_sha,
            name=check_run_name,
            result=review_result,
            error_message=None,
            external_id=f"pr-{context.pull_number}",
            details_url=details_url,
        )
    except (GitHubAPIError, httpx.HTTPError):
        logger.exception(
            "GitHub App publishing failed for %s/%s#%s",
            context.owner,
            context.repo,
            context.pull_number,
        )


async def create_check_run(
    *,
    installation_token: str,
    owner: str,
    repo: str,
    head_sha: str,
    name: str,
    result: PRReviewResult | None,
    error_message: str | None,
    external_id: str,
    details_url: str | None,
) -> None:
    """Create a completed GitHub Check Run summarizing the review result."""

    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/check-runs"
    headers = build_github_headers(github_token=installation_token)

    payload = {
        "name": name,
        "head_sha": head_sha,
        "status": "completed",
        "completed_at": datetime.now(UTC).isoformat(),
        "conclusion": _build_check_run_conclusion(result=result, error_message=error_message),
        "external_id": external_id,
        "output": _build_check_run_output(result=result, error_message=error_message),
    }
    if details_url is not None:
        payload["details_url"] = details_url

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    _parse_json_response(response, resource_name="check run")


async def create_pr_review_comment(
    *,
    installation_token: str,
    owner: str,
    repo: str,
    pull_number: int,
    result: PRReviewResult,
) -> str | None:
    """Post the full review to the PR conversation and return the comment URL."""

    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues/{pull_number}/comments"
    headers = build_github_headers(github_token=installation_token)
    payload = {"body": _build_pr_review_comment_body(result)}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise GitHubAPIError(
            "GitHub comment request failed before a response was received."
        ) from exc

    response_payload = _parse_json_response(response, resource_name="pull request comment")
    if not isinstance(response_payload, dict):
        return None
    html_url = response_payload.get("html_url")
    return html_url if isinstance(html_url, str) and html_url.strip() else None


async def create_pull_request_review(
    *,
    installation_token: str,
    owner: str,
    repo: str,
    pull_number: int,
    head_sha: str,
    changed_files: list[GitHubChangedFile],
    result: PRReviewResult,
) -> str | None:
    """Create a GitHub pull request review with resolvable inline threads."""

    review_draft = _build_structured_review_draft(result=result, changed_files=changed_files)
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
    headers = build_github_headers(github_token=installation_token)
    payload: dict[str, object] = {
        "commit_id": head_sha,
        "body": review_draft.body,
        "event": review_draft.event,
    }
    if review_draft.inline_threads:
        payload["comments"] = [
            {
                "path": thread.path,
                "line": thread.line,
                "side": thread.side,
                "body": thread.body,
            }
            for thread in review_draft.inline_threads
        ]

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise GitHubAPIError(
            "GitHub review request failed before a response was received."
        ) from exc

    response_payload = _parse_json_response(response, resource_name="pull request review")
    if not isinstance(response_payload, dict):
        return None

    html_url = response_payload.get("html_url")
    if isinstance(html_url, str) and html_url.strip():
        return html_url

    links_payload = response_payload.get("_links")
    if isinstance(links_payload, dict):
        html_payload = links_payload.get("html")
        if isinstance(html_payload, dict):
            href = html_payload.get("href")
            if isinstance(href, str) and href.strip():
                return href

    return None


async def try_publish_pull_request_review(
    *,
    installation_token: str,
    owner: str,
    repo: str,
    pull_number: int,
    head_sha: str,
    changed_files: list[GitHubChangedFile],
    result: PRReviewResult,
) -> str | None:
    """Publish a structured PR review and fall back to a timeline comment if needed."""

    try:
        return await create_pull_request_review(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            head_sha=head_sha,
            changed_files=changed_files,
            result=result,
        )
    except GitHubAPIError as exc:
        logger.warning(
            "Falling back to a PR comment because GitHub App could not create a review for "
            "%s/%s#%s: %s",
            owner,
            repo,
            pull_number,
            exc.detail,
        )
        return await try_create_pr_review_comment(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            result=result,
        )


async def try_create_pr_review_comment(
    *,
    installation_token: str,
    owner: str,
    repo: str,
    pull_number: int,
    result: PRReviewResult,
) -> str | None:
    """Try to post a full PR review comment and fall back cleanly on failure."""

    try:
        return await create_pr_review_comment(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            result=result,
        )
    except GitHubAPIError as exc:
        logger.warning(
            "Falling back to PR URL because GitHub App could not create a PR comment for "
            "%s/%s#%s: %s",
            owner,
            repo,
            pull_number,
            exc.detail,
        )
        return None


def _build_check_run_conclusion(
    *,
    result: PRReviewResult | None,
    error_message: str | None,
) -> str:
    if error_message is not None:
        return "failure"
    if result is None:
        return "neutral"

    conclusion_map = {
        MergeRecommendation.REQUEST_CHANGES: "action_required",
        MergeRecommendation.COMMENT: "neutral",
        MergeRecommendation.APPROVE: "success",
    }
    return conclusion_map[result.merge_recommendation]


def _build_structured_review_draft(
    *,
    result: PRReviewResult,
    changed_files: list[GitHubChangedFile],
) -> StructuredReviewDraft:
    file_line_sets = _build_diff_line_sets(changed_files)
    inline_threads: list[StructuredReviewThread] = []
    summary_only_comments: list[ReviewComment] = []

    for comment in result.visible_comments:
        thread = _build_structured_review_thread(
            comment=comment,
            file_line_sets=file_line_sets,
        )
        if thread is None:
            summary_only_comments.append(comment)
            continue
        inline_threads.append(thread)

    return StructuredReviewDraft(
        body=_build_structured_review_body(
            result=result,
            inline_threads_count=len(inline_threads),
            summary_only_comments=summary_only_comments,
        ),
        event=_build_pull_request_review_event(result),
        inline_threads=inline_threads,
    )


def _build_pull_request_review_event(result: PRReviewResult) -> str:
    event_map = {
        MergeRecommendation.REQUEST_CHANGES: "REQUEST_CHANGES",
        MergeRecommendation.COMMENT: "COMMENT",
        MergeRecommendation.APPROVE: "APPROVE",
    }
    return event_map[result.merge_recommendation]


def _build_structured_review_body(
    *,
    result: PRReviewResult,
    inline_threads_count: int,
    summary_only_comments: list[ReviewComment],
) -> str:
    highlighted_titles = [
        f"{index + 1}. [{comment.severity.upper()}] {comment.title}"
        for index, comment in enumerate(result.visible_comments[:5])
    ]
    hidden_comment_lines = [
        f"- {comment.title} ({comment.severity} severity, {comment.confidence} confidence)"
        for comment in result.hidden_comments
    ]
    file_summary_lines = [
        f"- `{file_summary.filename}` · {file_summary.change_type} · "
        f"{file_summary.risk_level} risk: {file_summary.summary}"
        for file_summary in result.file_summaries
    ]
    summary_only_lines = [
        _build_summary_only_comment_line(comment, index=index + 1)
        for index, comment in enumerate(summary_only_comments)
    ]

    sections = [
        "## SignalReview",
        (
            f"**{result.merge_recommendation.replace('_', ' ').title()} · "
            f"{result.overall_risk.title()} risk**"
        ),
        "",
        result.summary,
        "",
        "### Review Overview",
        f"- Inline review threads: **{inline_threads_count}**",
        f"- Summary-only findings: **{len(summary_only_comments)}**",
        f"- Hidden comments: **{result.hidden_comments_count}**",
        "",
        (
            "See the inline SignalReview threads in **Files changed** for the detailed findings. "
            "Those conversations can be resolved directly in GitHub once addressed."
        ),
    ]

    if highlighted_titles:
        sections.extend(["", "### Key Findings", *highlighted_titles])

    if summary_only_lines:
        sections.extend(
            [
                "",
                f"<details><summary>Summary-only findings ({len(summary_only_lines)})</summary>",
                "",
                "\n".join(summary_only_lines),
                "",
                "</details>",
            ]
        )

    if hidden_comment_lines:
        sections.extend(
            [
                "",
                f"<details><summary>Hidden comments ({result.hidden_comments_count})</summary>",
                "",
                "\n".join(hidden_comment_lines),
                "",
                "</details>",
            ]
        )

    if file_summary_lines:
        sections.extend(
            [
                "",
                "<details><summary>File summaries</summary>",
                "",
                "\n".join(file_summary_lines),
                "",
                "</details>",
            ]
        )

    return "\n".join(sections)


def _build_summary_only_comment_line(comment: ReviewComment, *, index: int) -> str:
    location = (
        f"`{comment.file}:{comment.line}`"
        if comment.file is not None and comment.line is not None
        else f"`{comment.file}`"
        if comment.file is not None
        else "Unknown location"
    )
    return (
        f"{index}. **{comment.title}** ({comment.severity} severity, "
        f"{comment.confidence} confidence) at {location}\n"
        f"   {comment.problem}"
    )


def _build_structured_review_thread(
    *,
    comment: ReviewComment,
    file_line_sets: dict[str, tuple[set[int], set[int]]],
) -> StructuredReviewThread | None:
    if comment.file is None or comment.line is None:
        return None

    anchor = _find_review_thread_anchor(
        filename=comment.file,
        line=comment.line,
        file_line_sets=file_line_sets,
    )
    if anchor is None:
        return None

    return StructuredReviewThread(
        path=comment.file,
        line=comment.line,
        side=anchor,
        body=_build_inline_thread_body(comment),
    )


def _build_inline_thread_body(comment: ReviewComment) -> str:
    header = (
        f"**{comment.title}**\n\n"
        f"{comment.severity.title()} severity · {comment.category.title()} · "
        f"{comment.confidence.title()} confidence"
    )
    problem_section = f"**Problem**\n{comment.problem}"

    detail_parts = [
        f"**Why it matters**\n{comment.why_it_matters}",
        f"**Suggested fix**\n{comment.suggestion}",
    ]
    suggestion_block = _build_github_suggestion_block(comment.code_suggestion)
    if suggestion_block is not None:
        detail_parts.append(suggestion_block)

    details_block = (
        "<details><summary>Details & suggested fix</summary>\n\n"
        + "\n\n".join(detail_parts)
        + "\n\n</details>"
    )

    return "\n\n".join([header, problem_section, details_block])


def _build_github_suggestion_block(code_suggestion: str | None) -> str | None:
    """Build a GitHub-appliable suggestion block for inline review comments."""

    if code_suggestion is None:
        return None

    normalized_suggestion = code_suggestion.strip("\n")
    if not normalized_suggestion.strip():
        return None

    return f"```suggestion\n{normalized_suggestion}\n```"


def _find_review_thread_anchor(
    *,
    filename: str,
    line: int,
    file_line_sets: dict[str, tuple[set[int], set[int]]],
) -> str | None:
    right_lines, left_lines = file_line_sets.get(filename, (set(), set()))
    if line in right_lines:
        return "RIGHT"
    if line in left_lines:
        return "LEFT"
    return None


def _build_diff_line_sets(
    changed_files: list[GitHubChangedFile],
) -> dict[str, tuple[set[int], set[int]]]:
    file_line_sets: dict[str, tuple[set[int], set[int]]] = {}

    for changed_file in changed_files:
        right_lines: set[int] = set()
        left_lines: set[int] = set()
        patch = changed_file.patch
        if patch is None:
            file_line_sets[changed_file.filename] = (right_lines, left_lines)
            continue

        old_line: int | None = None
        new_line: int | None = None
        malformed_patch = False
        for patch_line in patch.splitlines():
            hunk_match = _DIFF_HUNK_HEADER_PATTERN.match(patch_line)
            if hunk_match is not None:
                old_line = int(hunk_match.group("old"))
                new_line = int(hunk_match.group("new"))
                continue
            if old_line is None or new_line is None:
                malformed_patch = True
                logger.warning(
                    "Skipping inline review mapping for %s because the patch did not begin with "
                    "a valid hunk header.",
                    changed_file.filename,
                )
                break
            if patch_line.startswith("\\"):
                continue
            if patch_line.startswith("+"):
                right_lines.add(new_line)
                new_line += 1
                continue
            if patch_line.startswith("-"):
                left_lines.add(old_line)
                old_line += 1
                continue
            if not patch_line.startswith(" "):
                malformed_patch = True
                logger.warning(
                    "Skipping inline review mapping for %s because the patch contained an "
                    "unexpected diff line: %r",
                    changed_file.filename,
                    patch_line,
                )
                break

            right_lines.add(new_line)
            left_lines.add(old_line)
            old_line += 1
            new_line += 1

        if malformed_patch:
            file_line_sets[changed_file.filename] = (set(), set())
            continue

        file_line_sets[changed_file.filename] = (right_lines, left_lines)

    return file_line_sets


def _build_check_run_output(
    *,
    result: PRReviewResult | None,
    error_message: str | None,
) -> dict[str, str]:
    if error_message is not None:
        return {
            "title": "SignalReview could not complete this review",
            "summary": error_message,
            "text": "Check the SignalReview service logs for the full traceback.",
        }
    if result is None:
        return {
            "title": "SignalReview finished without a result",
            "summary": "No review result was available.",
            "text": "SignalReview did not produce a review payload for this pull request.",
        }

    visible_lines = [
        f"- {comment.title} ({comment.severity} severity, {comment.confidence} confidence)"
        for comment in result.visible_comments[:10]
    ]
    hidden_suffix = (
        "\n\n"
        f"{result.hidden_comments_count} lower-signal comments were hidden by the "
        "Signal Filter."
        if result.hidden_comments_count > 0
        else ""
    )
    text = "\n".join(visible_lines) if visible_lines else "No visible comments."
    title = (
        f"{result.merge_recommendation.replace('_', ' ').title()} · "
        f"{result.overall_risk.title()} risk"
    )

    return {
        "title": title,
        "summary": (
            f"{result.summary}\n\n"
            f"Visible comments: {result.visible_comments_count} · "
            f"Hidden comments: {result.hidden_comments_count}{hidden_suffix}"
        ),
        "text": text,
    }


def _build_pr_review_comment_body(result: PRReviewResult) -> str:
    visible_comment_sections = [
        _build_comment_markdown(comment, index=index + 1)
        for index, comment in enumerate(result.visible_comments)
    ]
    hidden_comment_sections = [
        _build_comment_markdown(comment, index=index + 1)
        for index, comment in enumerate(result.hidden_comments)
    ]
    file_summary_lines = [
        (
            f"- `{file_summary.filename}` · {file_summary.change_type} · "
            f"{file_summary.risk_level} risk\n"
            f"  {file_summary.summary}"
        )
        for file_summary in result.file_summaries
    ]

    sections = [
        "## SignalReview",
        (
            f"**{result.merge_recommendation.replace('_', ' ').title()} · "
            f"{result.overall_risk.title()} risk**"
        ),
        "",
        result.summary,
        "",
        (
            f"Visible comments: **{result.visible_comments_count}** · "
            f"Hidden comments: **{result.hidden_comments_count}**"
        ),
        "",
        "### Visible Comments",
    ]

    if visible_comment_sections:
        sections.extend(visible_comment_sections)
    else:
        sections.append("No visible comments.")

    if hidden_comment_sections:
        sections.extend(
            [
                "",
                f"<details><summary>Hidden comments ({result.hidden_comments_count})</summary>",
                "",
                "\n\n".join(hidden_comment_sections),
                "",
                "</details>",
            ]
        )

    if file_summary_lines:
        sections.extend(
            [
                "",
                "### File Summaries",
                "\n".join(file_summary_lines),
            ]
        )

    return "\n".join(sections)


def _build_comment_markdown(comment: ReviewComment, *, index: int) -> str:
    location = (
        f"`{comment.file}:{comment.line}`"
        if comment.file is not None and comment.line is not None
        else f"`{comment.file}`"
        if comment.file is not None
        else "Unknown location"
    )
    summary_line = (
        f"{index}. **{comment.title}** "
        f"— {comment.severity} · {comment.category} · {location}"
    )
    inner_parts = [
        (
            f"- Severity: **{comment.severity}**\n"
            f"- Confidence: **{comment.confidence}**\n"
            f"- Category: **{comment.category}**\n"
            f"- Location: {location}"
        ),
        f"**Problem**\n{comment.problem}",
        f"**Why it matters**\n{comment.why_it_matters}",
        f"**Suggested fix**\n{comment.suggestion}",
    ]
    if comment.code_suggestion is not None:
        inner_parts.append(f"```text\n{comment.code_suggestion}\n```")
    inner = "\n\n".join(inner_parts)
    return (
        f"<details><summary>{summary_line}</summary>\n\n"
        f"{inner}\n\n"
        f"</details>"
    )


def _parse_json_response(response: httpx.Response, *, resource_name: str) -> object:
    if response.status_code < 200 or response.status_code >= 300:
        raise GitHubAPIError(
            f"GitHub API returned {response.status_code} while creating {resource_name}."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise GitHubAPIError(
            f"GitHub API returned malformed JSON while creating {resource_name}."
        ) from exc


def _read_required_dict(
    payload: dict[str, object],
    key: str,
    error_message: str,
) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise GitHubWebhookPayloadError(error_message)
    return value


def _read_required_str(payload: dict[str, object], key: str, error_message: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GitHubWebhookPayloadError(error_message)
    return value


def _read_required_int(payload: dict[str, object], key: str, error_message: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GitHubWebhookPayloadError(error_message)
    return value
