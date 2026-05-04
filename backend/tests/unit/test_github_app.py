from typing import cast

import pytest

from src.exceptions.custom import GitHubAPIError
from src.models.responses import (
    FileSummary,
    MergeRecommendation,
    OverallRisk,
    PRReviewResult,
    ReviewCategory,
    ReviewComment,
    ReviewConfidence,
    ReviewSeverity,
)
from src.services.github import GitHubChangedFile
from src.services.github_app import (
    GITHUB_APP_REVIEWER_CONTEXT,
    PullRequestWebhookContext,
    _build_diff_line_sets,
    _build_github_suggestion_block,
    _build_pr_review_comment_body,
    _build_structured_review_draft,
    create_pr_review_comment,
    create_pull_request_review,
    handle_pull_request_webhook,
    try_publish_pull_request_review,
)


def _review_result() -> PRReviewResult:
    return PRReviewResult(
        pr_title="Improve GitHub App comment publishing",
        pr_author="octocat",
        pr_url="https://github.com/octocat/hello-world/pull/42",
        overall_risk=OverallRisk.MEDIUM,
        merge_recommendation=MergeRecommendation.COMMENT,
        summary="Adds a PR comment publishing path for GitHub App reviews.",
        visible_comments=[
            ReviewComment(
                title="Add coverage for malformed GitHub responses",
                file="backend/src/services/github_app.py",
                line=302,
                category=ReviewCategory.TESTS,
                severity=ReviewSeverity.MEDIUM,
                confidence=ReviewConfidence.HIGH,
                problem="The new GitHub comment posting flow needs regression coverage.",
                why_it_matters="Unexpected API payloads can silently break details links.",
                suggestion="Add unit tests for success and malformed response cases.",
                code_suggestion=None,
            )
        ],
        hidden_comments=[
            ReviewComment(
                title="Consider deduplicating repeated PR comments",
                file="backend/src/services/github_app.py",
                line=330,
                category=ReviewCategory.LOGIC,
                severity=ReviewSeverity.LOW,
                confidence=ReviewConfidence.MEDIUM,
                problem="Repeated synchronize events may create many top-level comments.",
                why_it_matters="High-volume PRs could get noisy over time.",
                suggestion=(
                    "Store and update a prior SignalReview comment instead of posting a new one."
                ),
                code_suggestion=None,
            )
        ],
        total_comments=2,
        visible_comments_count=1,
        hidden_comments_count=1,
        signal_filter_summary="1 high-signal comment visible. 1 lower-signal comment hidden.",
        file_summaries=[
            FileSummary(
                filename="backend/src/services/github_app.py",
                change_type="modified",
                risk_level=OverallRisk.MEDIUM,
                summary="Adds PR comment publishing and details link handling.",
            )
        ],
    )


def _changed_files() -> list[GitHubChangedFile]:
    return [
        GitHubChangedFile(
            filename="backend/src/services/github_app.py",
            status="modified",
            additions=4,
            deletions=0,
            changes=4,
            patch=(
                "@@ -298,3 +298,7 @@ async def create_pr_review_comment(\n"
                "     payload = {\"body\": _build_pr_review_comment_body(result)}\n"
                " \n"
                "+    response_payload = _parse_json_response(\n"
                "+        response, resource_name=\"comment\"\n"
                "+    )\n"
                "+    if not isinstance(response_payload, dict):\n"
                "+        return None\n"
                "+\n"
                "     html_url = response_payload.get(\"html_url\")\n"
                "     return html_url if isinstance(html_url, str) and html_url.strip() else None\n"
            ),
        )
    ]


def test_build_pr_review_comment_body_contains_visible_and_hidden_sections() -> None:
    body = _build_pr_review_comment_body(_review_result())

    assert "## SignalReview" in body
    assert "### Visible Comments" in body
    assert "Add coverage for malformed GitHub responses" in body
    assert "<details><summary>Hidden comments (1)</summary>" in body
    assert "### File Summaries" in body


def test_build_structured_review_draft_creates_inline_threads_and_summary_fallbacks() -> None:
    extra_comment = ReviewComment(
        title="Follow up on fallback logging",
        file=None,
        line=None,
        category=ReviewCategory.LOGIC,
        severity=ReviewSeverity.LOW,
        confidence=ReviewConfidence.MEDIUM,
        problem="A summary-only note should stay in the review body when no diff anchor exists.",
        why_it_matters="Unanchored comments should remain visible without blocking inline threads.",
        suggestion="Keep these comments in the summary section.",
        code_suggestion=None,
    )
    result = _review_result().model_copy(
        update={"visible_comments": [*_review_result().visible_comments, extra_comment]}
    )

    draft = _build_structured_review_draft(result=result, changed_files=_changed_files())

    assert draft.event == "COMMENT"
    assert len(draft.inline_threads) == 1
    assert draft.inline_threads[0].path == "backend/src/services/github_app.py"
    assert draft.inline_threads[0].line == 302
    assert draft.inline_threads[0].side == "RIGHT"
    assert "See the inline SignalReview threads in **Files changed**" in draft.body
    assert "Summary-only findings" in draft.body
    assert "Follow up on fallback logging" in draft.body


def test_build_github_suggestion_block_formats_applyable_fence() -> None:
    suggestion_block = _build_github_suggestion_block(
        "if response_payload is None:\n    return None"
    )

    assert suggestion_block == (
        "```suggestion\n"
        "if response_payload is None:\n"
        "    return None\n"
        "```"
    )


def test_build_github_suggestion_block_ignores_blank_suggestions() -> None:
    assert _build_github_suggestion_block(None) is None
    assert _build_github_suggestion_block("\n\n") is None


def test_build_structured_review_draft_uses_summary_only_when_patch_missing() -> None:
    changed_files = [
        GitHubChangedFile(
            filename="backend/src/services/github_app.py",
            status="modified",
            additions=0,
            deletions=0,
            changes=0,
            patch=None,
        )
    ]

    draft = _build_structured_review_draft(result=_review_result(), changed_files=changed_files)

    assert draft.inline_threads == []
    assert "Summary-only findings" in draft.body
    assert "Add coverage for malformed GitHub responses" in draft.body


def test_build_diff_line_sets_skips_malformed_patch() -> None:
    changed_files = [
        GitHubChangedFile(
            filename="backend/src/services/github_app.py",
            status="modified",
            additions=1,
            deletions=0,
            changes=1,
            patch=(
                "this is not a valid diff line\n"
                "+added line without a hunk header\n"
            ),
        )
    ]

    file_line_sets = _build_diff_line_sets(changed_files)

    assert file_line_sets["backend/src/services/github_app.py"] == (set(), set())


def test_build_structured_review_draft_handles_mixed_inline_and_summary_comments() -> None:
    extra_comment = ReviewComment(
        title="Line anchor missing from malformed patch",
        file="backend/src/services/missing_patch.py",
        line=99,
        category=ReviewCategory.LOGIC,
        severity=ReviewSeverity.MEDIUM,
        confidence=ReviewConfidence.HIGH,
        problem="The patch cannot be anchored cleanly.",
        why_it_matters="The finding should still appear in the summary.",
        suggestion="Keep it as a summary-only finding.",
        code_suggestion=None,
    )
    result = _review_result().model_copy(
        update={"visible_comments": [*_review_result().visible_comments, extra_comment]}
    )
    changed_files = [
        *_changed_files(),
        GitHubChangedFile(
            filename="backend/src/services/missing_patch.py",
            status="modified",
            additions=1,
            deletions=0,
            changes=1,
            patch="not-a-valid-hunk",
        ),
    ]

    draft = _build_structured_review_draft(result=result, changed_files=changed_files)

    assert len(draft.inline_threads) == 1
    assert draft.inline_threads[0].path == "backend/src/services/github_app.py"
    assert "Line anchor missing from malformed patch" in draft.body
    assert "Summary-only findings" in draft.body


@pytest.mark.asyncio
async def test_create_pr_review_comment_returns_comment_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 201

        def json(self) -> dict[str, str]:
            return {"html_url": "https://github.com/octocat/hello-world/pull/42#issuecomment-1"}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("src.services.github_app.httpx.AsyncClient", lambda timeout: FakeClient())

    comment_url = await create_pr_review_comment(
        installation_token="token",
        owner="octocat",
        repo="hello-world",
        pull_number=42,
        result=_review_result(),
    )

    assert comment_url == "https://github.com/octocat/hello-world/pull/42#issuecomment-1"


@pytest.mark.asyncio
async def test_create_pull_request_review_returns_review_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[dict[str, object]] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"html_url": "https://github.com/octocat/hello-world/pull/42/files#review-1"}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            payload = cast(dict[str, object], kwargs["json"])
            captured_payloads.append(payload)
            return FakeResponse()

    monkeypatch.setattr("src.services.github_app.httpx.AsyncClient", lambda timeout: FakeClient())

    review_url = await create_pull_request_review(
        installation_token="token",
        owner="octocat",
        repo="hello-world",
        pull_number=42,
        head_sha="abc123",
        changed_files=_changed_files(),
        result=_review_result(),
    )

    assert review_url == "https://github.com/octocat/hello-world/pull/42/files#review-1"
    assert captured_payloads[0]["event"] == "COMMENT"
    assert captured_payloads[0]["commit_id"] == "abc123"
    comments = cast(list[dict[str, object]], captured_payloads[0]["comments"])
    assert comments[0]["path"] == "backend/src/services/github_app.py"
    assert comments[0]["line"] == 302
    assert comments[0]["side"] == "RIGHT"
    assert "Problem" in cast(str, comments[0]["body"])


@pytest.mark.asyncio
async def test_create_pull_request_review_includes_github_suggestion_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads: list[dict[str, object]] = []
    result = _review_result().model_copy(
        update={
            "visible_comments": [
                ReviewComment(
                    title="Return early on invalid payload",
                    file="backend/src/services/github_app.py",
                    line=302,
                    category=ReviewCategory.LOGIC,
                    severity=ReviewSeverity.MEDIUM,
                    confidence=ReviewConfidence.HIGH,
                    problem="The payload should short-circuit on invalid data.",
                    why_it_matters="This avoids broken details links.",
                    suggestion="Return early when the payload is missing.",
                    code_suggestion="if response_payload is None:\n    return None",
                )
            ]
        }
    )

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"html_url": "https://github.com/octocat/hello-world/pull/42/files#review-1"}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            captured_payloads.append(cast(dict[str, object], kwargs["json"]))
            return FakeResponse()

    monkeypatch.setattr("src.services.github_app.httpx.AsyncClient", lambda timeout: FakeClient())

    await create_pull_request_review(
        installation_token="token",
        owner="octocat",
        repo="hello-world",
        pull_number=42,
        head_sha="abc123",
        changed_files=_changed_files(),
        result=result,
    )

    comments = cast(list[dict[str, object]], captured_payloads[0]["comments"])
    assert "```suggestion" in cast(str, comments[0]["body"])
    assert "if response_payload is None:" in cast(str, comments[0]["body"])


@pytest.mark.asyncio
async def test_try_publish_pull_request_review_falls_back_to_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_pull_request_review(**_: object) -> str | None:
        raise GitHubAPIError("forbidden")

    async def fake_try_create_pr_review_comment(**_: object) -> str | None:
        return "https://github.com/octocat/hello-world/pull/42#issuecomment-1"

    monkeypatch.setattr(
        "src.services.github_app.create_pull_request_review",
        fake_create_pull_request_review,
    )
    monkeypatch.setattr(
        "src.services.github_app.try_create_pr_review_comment",
        fake_try_create_pr_review_comment,
    )

    result = await try_publish_pull_request_review(
        installation_token="token",
        owner="octocat",
        repo="hello-world",
        pull_number=42,
        head_sha="abc123",
        changed_files=_changed_files(),
        result=_review_result(),
    )

    assert result == "https://github.com/octocat/hello-world/pull/42#issuecomment-1"


@pytest.mark.asyncio
async def test_handle_pull_request_webhook_passes_internal_reviewer_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_repo_context: list[str | None] = []
    captured_details_url: list[str | None] = []

    async def fake_request_installation_token(*, installation_id: int) -> str:
        assert installation_id == 12345
        return "installation-token"

    async def fake_perform_pr_review(**kwargs: object) -> PRReviewResult:
        captured_repo_context.append(
            cast(str | None, kwargs["repo_context"] if "repo_context" in kwargs else None)
        )
        return _review_result()

    async def fake_fetch_pr_files(**_: object) -> list[GitHubChangedFile]:
        return _changed_files()

    async def fake_try_publish_pull_request_review(**_: object) -> str | None:
        return "https://github.com/octocat/hello-world/pull/42/files#review-2"

    async def fake_create_check_run(**kwargs: object) -> None:
        captured_details_url.append(
            cast(str | None, kwargs["details_url"] if "details_url" in kwargs else None)
        )

    monkeypatch.setattr(
        "src.services.github_app.request_installation_token",
        fake_request_installation_token,
    )
    monkeypatch.setattr("src.services.github_app.perform_pr_review", fake_perform_pr_review)
    monkeypatch.setattr(
        "src.services.github_app.fetch_pr_files",
        fake_fetch_pr_files,
    )
    monkeypatch.setattr(
        "src.services.github_app.try_publish_pull_request_review",
        fake_try_publish_pull_request_review,
    )
    monkeypatch.setattr("src.services.github_app.create_check_run", fake_create_check_run)

    await handle_pull_request_webhook(
        PullRequestWebhookContext(
            action="synchronize",
            installation_id=12345,
            owner="octocat",
            repo="hello-world",
            pull_number=42,
            head_sha="abc123",
            pr_url="https://github.com/octocat/hello-world/pull/42",
        )
    )

    assert captured_repo_context == [GITHUB_APP_REVIEWER_CONTEXT]
    assert captured_details_url == ["https://github.com/octocat/hello-world/pull/42/files#review-2"]


@pytest.mark.asyncio
async def test_handle_pull_request_webhook_posts_failure_check_without_reraising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_failure_messages: list[str | None] = []

    async def fake_request_installation_token(*, installation_id: int) -> str:
        assert installation_id == 12345
        return "installation-token"

    async def fake_perform_pr_review(**_: object) -> PRReviewResult:
        raise GitHubAPIError("Claude returned malformed review JSON.")

    async def fake_create_check_run(**kwargs: object) -> None:
        captured_failure_messages.append(
            cast(str | None, kwargs["error_message"] if "error_message" in kwargs else None)
        )

    monkeypatch.setattr(
        "src.services.github_app.request_installation_token",
        fake_request_installation_token,
    )
    monkeypatch.setattr("src.services.github_app.perform_pr_review", fake_perform_pr_review)
    monkeypatch.setattr("src.services.github_app.create_check_run", fake_create_check_run)

    await handle_pull_request_webhook(
        PullRequestWebhookContext(
            action="synchronize",
            installation_id=12345,
            owner="octocat",
            repo="hello-world",
            pull_number=42,
            head_sha="abc123",
            pr_url="https://github.com/octocat/hello-world/pull/42",
        )
    )

    assert captured_failure_messages == ["Claude returned malformed review JSON."]


@pytest.mark.asyncio
async def test_handle_pull_request_webhook_reports_file_fetch_failures_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_failure_messages: list[str | None] = []

    async def fake_request_installation_token(*, installation_id: int) -> str:
        assert installation_id == 12345
        return "installation-token"

    async def fake_perform_pr_review(**_: object) -> PRReviewResult:
        return _review_result()

    async def fake_fetch_pr_files(**_: object) -> list[GitHubChangedFile]:
        raise GitHubAPIError("secondary rate limit")

    async def fake_create_check_run(**kwargs: object) -> None:
        captured_failure_messages.append(
            cast(str | None, kwargs["error_message"] if "error_message" in kwargs else None)
        )

    monkeypatch.setattr(
        "src.services.github_app.request_installation_token",
        fake_request_installation_token,
    )
    monkeypatch.setattr("src.services.github_app.perform_pr_review", fake_perform_pr_review)
    monkeypatch.setattr("src.services.github_app.fetch_pr_files", fake_fetch_pr_files)
    monkeypatch.setattr("src.services.github_app.create_check_run", fake_create_check_run)

    await handle_pull_request_webhook(
        PullRequestWebhookContext(
            action="synchronize",
            installation_id=12345,
            owner="octocat",
            repo="hello-world",
            pull_number=42,
            head_sha="abc123",
            pr_url="https://github.com/octocat/hello-world/pull/42",
        )
    )

    assert captured_failure_messages == ["GitHub PR file fetch failed: secondary rate limit"]


@pytest.mark.asyncio
async def test_run_pull_request_webhook_task_swallows_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_handle_pull_request_webhook(_: PullRequestWebhookContext) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "src.routers.github_webhooks.handle_pull_request_webhook",
        fake_handle_pull_request_webhook,
    )

    from src.routers.github_webhooks import run_pull_request_webhook_task

    await run_pull_request_webhook_task(
        PullRequestWebhookContext(
            action="synchronize",
            installation_id=12345,
            owner="octocat",
            repo="hello-world",
            pull_number=42,
            head_sha="abc123",
            pr_url="https://github.com/octocat/hello-world/pull/42",
        )
    )
