"""Request models for review workflows."""

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

GITHUB_PR_URL_PATTERN = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/\d+/?$")


class ReviewFocus(StrEnum):
    SECURITY = "security"
    LOGIC = "logic"
    TESTS = "tests"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    STYLE = "style"


class ReviewStrictness(StrEnum):
    QUIET = "quiet"
    BALANCED = "balanced"
    STRICT = "strict"


class PRReviewRequest(BaseModel):
    """Request payload for PR review analysis."""

    github_url: str
    repo_context: str | None = None
    focus_areas: list[ReviewFocus] = Field(
        default_factory=lambda: [
            ReviewFocus.SECURITY,
            ReviewFocus.LOGIC,
            ReviewFocus.TESTS,
        ]
    )
    strictness: ReviewStrictness = ReviewStrictness.BALANCED

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        normalized_value = value.strip()
        if not GITHUB_PR_URL_PATTERN.fullmatch(normalized_value):
            raise ValueError(
                "github_url must match https://github.com/{owner}/{repo}/pull/{number}"
            )
        return normalized_value
