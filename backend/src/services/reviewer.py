"""Anthropic reviewer integration."""

import json

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from src.config import get_settings
from src.exceptions.custom import ReviewerAPIError
from src.models.requests import ReviewFocus
from src.models.responses import (
    FileSummary,
    MergeRecommendation,
    OverallRisk,
    RawAIReviewResult,
    ReviewCategory,
    ReviewComment,
    ReviewConfidence,
    ReviewSeverity,
)
from src.services.github import SAMPLE_PULL_REQUEST_URL, GitHubPRMetadata

SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing a pull request. Your job is to produce "
    "high-signal code review comments only.\n\n"
    "You are not trying to find every possible nitpick. You are trying to identify issues "
    "that would matter in a real PR review.\n\n"
    "Rules:\n"
    "1. Only report issues grounded in the diff or supplied repo context.\n"
    "2. Do not invent files, functions, APIs, or requirements.\n"
    "3. If the diff alone is insufficient, say the issue depends on missing context and lower "
    "the confidence.\n"
    "4. Do not comment on formatting or style unless Style was selected.\n"
    "5. Do not comment on performance unless Performance was selected.\n"
    "6. Prefer security, correctness, data-loss, missing validation, missing authorization, "
    "error handling, broken tests, and missing tests for changed behavior.\n"
    "7. Every issue must include severity, confidence, category, file/line if visible, "
    "problem, why_it_matters, and suggestion.\n"
    "8. Keep comments concise and actionable.\n"
    "9. Avoid vague comments like 'consider improving this.'\n"
    "10. Do not suggest generic 'missing validation', 'missing authentication', "
    "'missing authorization', or 'sanitize inputs' issues unless the diff shows an externally "
    "reachable boundary or untrusted input path that is actually mishandled.\n"
    "11. Do not treat internal helper functions, installation tokens created by trusted code, "
    "or already-validated typed objects as suspicious by default.\n"
    "12. Do not infer security issues from logging, error handling, or API calls unless the diff "
    "shows sensitive values being logged, returned, persisted, or exposed.\n"
    "13. If the PR title conflicts with the visible diff, ignore the title and review the code "
    "that is actually changed.\n"
    "14. Missing tests are only worth reporting when the diff adds or changes behavior and there "
    "is no visible test coverage for that behavior in the diff.\n"
    "15. If no strong issues exist, return an empty comments array.\n"
    "16. Return JSON only. No markdown outside JSON."
)
REPAIR_SYSTEM_PROMPT = (
    "You convert malformed code review JSON into valid JSON matching an exact schema.\n\n"
    "Rules:\n"
    "1. Return JSON only.\n"
    "2. Preserve the original review meaning where possible.\n"
    "3. Fill required top-level fields conservatively if they are missing.\n"
    "4. Every comment must include title, severity, confidence, category, problem, "
    "why_it_matters, and suggestion.\n"
    "5. If a field is unknown, use a safe conservative default rather than omitting it.\n"
    "6. Do not add issues that are not present in the source material."
)

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


async def analyze_pr(
    metadata: GitHubPRMetadata,
    combined_diff: str,
    repo_context: str | None,
    focus_areas: list[ReviewFocus],
) -> RawAIReviewResult:
    """Analyze a pull request diff and return structured review comments."""

    settings = get_settings()
    if settings.anthropic_api_key is None or metadata.html_url == SAMPLE_PULL_REQUEST_URL:
        return _build_mock_review(metadata=metadata, demo_mode=settings.anthropic_api_key is None)

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = _build_user_prompt(
        metadata=metadata,
        combined_diff=combined_diff,
        repo_context=repo_context,
        focus_areas=focus_areas,
    )

    try:
        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2_000,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        raise ReviewerAPIError(
            f"Anthropic review request failed: {exc.__class__.__name__}: {exc}"
        ) from exc

    response_text = _extract_response_text(response.model_dump())
    if not response_text:
        raise ReviewerAPIError("Anthropic returned an empty review response.")

    return await _validate_or_repair_review_json(
        client=client,
        response_text=response_text,
    )


def _build_user_prompt(
    *,
    metadata: GitHubPRMetadata,
    combined_diff: str,
    repo_context: str | None,
    focus_areas: list[ReviewFocus],
) -> str:
    schema_description = json.dumps(RawAIReviewResult.model_json_schema(), indent=2)
    selected_focus_areas = ", ".join(focus_area.value for focus_area in focus_areas)
    repo_context_text = repo_context if repo_context else "No additional repo context provided."
    return f"""
Review this pull request and return JSON only.

PR title: {metadata.title}
PR author: {metadata.author}
PR URL: {metadata.html_url}
Base branch: {metadata.base_branch}
Head branch: {metadata.head_branch}
Focus areas: {selected_focus_areas}

Repo context:
{repo_context_text}

Combined diff:
{combined_diff}

Return JSON matching this schema exactly:
{schema_description}

Important review constraints:
- Prefer evidence from the diff over PR title wording.
- Do not raise generic security concerns about trusted internal code paths.
- Only flag missing tests when changed behavior is visible and untested in the diff.
""".strip()


async def _repair_review_json(
    *,
    client: AsyncAnthropic,
    malformed_response: str,
) -> str:
    schema_description = json.dumps(RawAIReviewResult.model_json_schema(), indent=2)
    repair_prompt = f"""
The following content is intended to be a code review result, but it does not match the required
schema. Rewrite it so it matches the schema exactly.

Return JSON only.

Required schema:
{schema_description}

Malformed content to repair:
{malformed_response}
""".strip()

    try:
        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2_000,
            temperature=0,
            system=REPAIR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": repair_prompt}],
        )
    except Exception as exc:
        raise ReviewerAPIError(
            f"Anthropic review repair request failed: {exc.__class__.__name__}: {exc}"
        ) from exc

    response_text = _extract_response_text(response.model_dump())
    if not response_text:
        raise ReviewerAPIError("Anthropic returned an empty repair response.")
    return response_text


async def _validate_or_repair_review_json(
    *,
    client: AsyncAnthropic,
    response_text: str,
) -> RawAIReviewResult:
    """Validate the primary response, then make at most one repair attempt."""

    try:
        return _validate_review_json(response_text)
    except ValidationError:
        repaired_response_text = await _repair_review_json(
            client=client,
            malformed_response=response_text,
        )
        try:
            return _validate_review_json(repaired_response_text)
        except ValidationError as repair_exc:
            raise ReviewerAPIError("Claude returned malformed review JSON.") from repair_exc


def _validate_review_json(response_text: str) -> RawAIReviewResult:
    """Parse a single JSON response without retries or recursive repair behavior."""

    return RawAIReviewResult.model_validate_json(_strip_markdown_fences(response_text))


def _extract_response_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def _strip_markdown_fences(response_text: str) -> str:
    stripped = response_text.strip()
    if stripped.startswith("```json"):
        stripped = stripped.removeprefix("```json").strip()
    elif stripped.startswith("```"):
        stripped = stripped.removeprefix("```").strip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].strip()
    return stripped


def _build_mock_review(metadata: GitHubPRMetadata, *, demo_mode: bool) -> RawAIReviewResult:
    summary = (
        "This PR adds a user profile endpoint. The main issue is that the visible code "
        "authenticates the request but does not show an object-level authorization check "
        "before returning user data."
    )
    if demo_mode and metadata.html_url != SAMPLE_PULL_REQUEST_URL:
        summary = (
            "Demo mode is active because ANTHROPIC_API_KEY is not configured. This mock review "
            "illustrates the kind of high-signal authorization issue SignalReview surfaces."
        )

    return RawAIReviewResult(
        overall_risk=OverallRisk.HIGH,
        merge_recommendation=MergeRecommendation.REQUEST_CHANGES,
        summary=summary,
        comments=[
            ReviewComment(
                title="Missing object-level authorization on user lookup",
                file="routes/users.ts",
                line=24,
                category=ReviewCategory.SECURITY,
                severity=ReviewSeverity.HIGH,
                confidence=ReviewConfidence.HIGH,
                problem=(
                    "The endpoint fetches a user by ID and returns it, but the visible code "
                    "does not verify that the authenticated user owns that ID or has admin "
                    "permissions."
                ),
                why_it_matters=(
                    "A logged-in user may be able to access another user's private data by "
                    "changing the ID in the URL."
                ),
                suggestion=(
                    "Before returning the user, check that req.user.id matches the requested ID "
                    "or that the requester has an admin role. Return 403 if access is not allowed."
                ),
                code_suggestion=(
                    "if (req.user.id !== req.params.id && req.user.role !== \"admin\") {\n"
                    "  return res.status(403).json({ error: \"Forbidden\" });\n"
                    "}"
                ),
            ),
            ReviewComment(
                title="Add regression test for unauthorized access",
                file="routes/users.test.ts",
                line=None,
                category=ReviewCategory.TESTS,
                severity=ReviewSeverity.MEDIUM,
                confidence=ReviewConfidence.HIGH,
                problem=(
                    "The PR changes access to user data, but there is no visible test proving "
                    "that one user cannot access another user's profile."
                ),
                why_it_matters=(
                    "Authorization bugs can silently reappear unless they are covered by tests."
                ),
                suggestion=(
                    "Add a test where User A attempts to fetch User B's profile and assert "
                    "that the endpoint returns 403."
                ),
                code_suggestion=None,
            ),
            ReviewComment(
                title="No rate limiting on the profile endpoint",
                file="routes/users.ts",
                line=20,
                category=ReviewCategory.LOGIC,
                severity=ReviewSeverity.MEDIUM,
                confidence=ReviewConfidence.MEDIUM,
                problem=(
                    "The new endpoint has no rate limiting. An attacker could enumerate user "
                    "profiles at high speed once they have a valid session token."
                ),
                why_it_matters=(
                    "Without rate limiting, a single compromised account can be used to scrape "
                    "the entire user base."
                ),
                suggestion=(
                    "Apply an existing rate-limit middleware to this route, or add a per-user "
                    "request cap using a token bucket on the session ID."
                ),
                code_suggestion=None,
            ),
            ReviewComment(
                title="Consider returning a narrowed user DTO",
                file="routes/users.ts",
                line=28,
                category=ReviewCategory.SECURITY,
                severity=ReviewSeverity.LOW,
                confidence=ReviewConfidence.MEDIUM,
                problem=(
                    "The endpoint appears to return the full user object. Depending on the schema, "
                    "this could expose fields the client does not need."
                ),
                why_it_matters=(
                    "Returning full database records can accidentally expose sensitive or "
                    "internal fields."
                ),
                suggestion=(
                    "Return only the fields needed by the client, such as id, name, and avatarUrl."
                ),
                code_suggestion=None,
            ),
        ],
        file_summaries=[
            FileSummary(
                filename="routes/users.ts",
                change_type="modified",
                risk_level=OverallRisk.HIGH,
                summary=(
                    "Adds a user profile endpoint but does not show object-level authorization "
                    "before returning user data."
                ),
            ),
            FileSummary(
                filename="routes/users.test.ts",
                change_type="added",
                risk_level=OverallRisk.MEDIUM,
                summary="Adds a happy-path test only; missing negative authorization coverage.",
            ),
        ],
    )
