"""Response models for review workflows."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewCategory(StrEnum):
    SECURITY = "security"
    LOGIC = "logic"
    TESTS = "tests"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    STYLE = "style"


class ReviewSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MergeRecommendation(StrEnum):
    APPROVE = "approve"
    COMMENT = "comment"
    REQUEST_CHANGES = "request_changes"


class OverallRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewComment(BaseModel):
    title: str
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    category: ReviewCategory
    severity: ReviewSeverity
    confidence: ReviewConfidence
    problem: str
    why_it_matters: str
    suggestion: str
    code_suggestion: str | None = None
    is_hidden_by_default: bool = False


class FileSummary(BaseModel):
    filename: str
    change_type: str
    risk_level: OverallRisk
    summary: str


class RawAIReviewResult(BaseModel):
    overall_risk: OverallRisk
    merge_recommendation: MergeRecommendation
    summary: str
    comments: list[ReviewComment]
    file_summaries: list[FileSummary]


class PRReviewResult(BaseModel):
    pr_title: str
    pr_author: str
    pr_url: str
    overall_risk: OverallRisk
    merge_recommendation: MergeRecommendation
    summary: str
    visible_comments: list[ReviewComment]
    hidden_comments: list[ReviewComment]
    total_comments: int
    visible_comments_count: int
    hidden_comments_count: int
    signal_filter_summary: str
    file_summaries: list[FileSummary]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
