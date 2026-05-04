"""Shared PR review orchestration."""

from src.models.requests import ReviewFocus, ReviewStrictness
from src.models.responses import PRReviewResult
from src.services.github import build_combined_diff, fetch_pr_files, fetch_pr_metadata
from src.services.reviewer import analyze_pr
from src.services.signal_filter import apply_signal_filter, build_signal_filter_summary


async def perform_pr_review(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    repo_context: str | None,
    focus_areas: list[ReviewFocus],
    strictness: ReviewStrictness,
    github_token: str | None = None,
) -> PRReviewResult:
    """Run the complete PR review pipeline and return the typed result."""

    metadata = await fetch_pr_metadata(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        github_token=github_token,
    )
    files = await fetch_pr_files(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        github_token=github_token,
    )
    combined_diff = build_combined_diff(files)
    raw_review = await analyze_pr(
        metadata=metadata,
        combined_diff=combined_diff,
        repo_context=repo_context,
        focus_areas=focus_areas,
    )
    visible_comments, hidden_comments = apply_signal_filter(
        comments=raw_review.comments,
        strictness=strictness,
    )

    return PRReviewResult(
        pr_title=metadata.title,
        pr_author=metadata.author,
        pr_url=metadata.html_url,
        overall_risk=raw_review.overall_risk,
        merge_recommendation=raw_review.merge_recommendation,
        summary=raw_review.summary,
        visible_comments=visible_comments,
        hidden_comments=hidden_comments,
        total_comments=len(raw_review.comments),
        visible_comments_count=len(visible_comments),
        hidden_comments_count=len(hidden_comments),
        signal_filter_summary=build_signal_filter_summary(
            visible=visible_comments,
            hidden=hidden_comments,
            strictness=strictness,
        ),
        file_summaries=raw_review.file_summaries,
    )
