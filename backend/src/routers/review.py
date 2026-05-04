"""Review endpoints."""

from fastapi import APIRouter

from src.config import get_settings
from src.models.requests import PRReviewRequest
from src.models.responses import PRReviewResult
from src.services.github import parse_pr_url
from src.services.review_flow import perform_pr_review

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}


@router.post("/review", response_model=PRReviewResult)
async def review_pull_request(request: PRReviewRequest) -> PRReviewResult:
    parsed_pr = parse_pr_url(request.github_url)
    return await perform_pr_review(
        owner=parsed_pr.owner,
        repo=parsed_pr.repo,
        pull_number=parsed_pr.pull_number,
        repo_context=request.repo_context,
        focus_areas=request.focus_areas,
        strictness=request.strictness,
    )
