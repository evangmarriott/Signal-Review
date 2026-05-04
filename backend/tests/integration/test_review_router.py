from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from src.models.requests import ReviewFocus, ReviewStrictness
from src.models.responses import (
    FileSummary,
    MergeRecommendation,
    OverallRisk,
    PRReviewResult,
)
from src.services.github import ParsedPullRequest


def test_get_api_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_post_api_review_invalid_url_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/review",
        json={
            "github_url": "https://github.com/octocat/hello-world/issues/42",
            "focus_areas": ["security", "logic", "tests"],
            "strictness": "balanced",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_post_api_review_success_with_mocked_services_returns_visible_and_hidden_counts(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_perform_pr_review(
        *,
        owner: str,
        repo: str,
        pull_number: int,
        repo_context: str | None,
        focus_areas: list[ReviewFocus],
        strictness: ReviewStrictness,
        github_token: str | None = None,
    ) -> PRReviewResult:
        assert owner == "octocat"
        assert repo == "hello-world"
        assert pull_number == 42
        assert repo_context == "Team rule: user endpoints need object-level authorization."
        assert focus_areas == [ReviewFocus.SECURITY, ReviewFocus.LOGIC, ReviewFocus.TESTS]
        assert strictness == ReviewStrictness.BALANCED
        assert github_token is None
        return PRReviewResult(
            pr_title="Add user profile endpoint",
            pr_author="demo-user",
            pr_url="https://github.com/octocat/hello-world/pull/42",
            overall_risk=OverallRisk.HIGH,
            merge_recommendation=MergeRecommendation.REQUEST_CHANGES,
            summary="A high-signal security issue was found.",
            visible_comments=[],
            hidden_comments=[],
            total_comments=2,
            visible_comments_count=1,
            hidden_comments_count=1,
            signal_filter_summary="1 high-signal comment visible. 1 lower-signal comment hidden.",
            file_summaries=[
                FileSummary(
                    filename="routes/users.ts",
                    change_type="modified",
                    risk_level=OverallRisk.HIGH,
                    summary="Adds a profile endpoint.",
                )
            ],
        )

    monkeypatch.setattr(
        "src.routers.review.parse_pr_url",
        lambda _: ParsedPullRequest("octocat", "hello-world", 42),
    )
    monkeypatch.setattr("src.routers.review.perform_pr_review", fake_perform_pr_review)

    response = client.post(
        "/api/review",
        json={
            "github_url": "https://github.com/octocat/hello-world/pull/42",
            "repo_context": "Team rule: user endpoints need object-level authorization.",
            "focus_areas": ["security", "logic", "tests"],
            "strictness": "balanced",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pr_title"] == "Add user profile endpoint"
    assert payload["visible_comments_count"] == 1
    assert payload["hidden_comments_count"] == 1
    assert payload["total_comments"] == 2
