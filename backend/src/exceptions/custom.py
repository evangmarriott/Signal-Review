"""Custom exceptions for SignalReview."""


class SignalReviewError(Exception):
    """Base application exception."""

    error = "signal_review_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidGitHubURLError(SignalReviewError):
    error = "invalid_github_url"


class PRNotFoundError(SignalReviewError):
    error = "pr_not_found"


class GitHubAPIError(SignalReviewError):
    error = "github_api_error"


class ReviewerAPIError(SignalReviewError):
    error = "reviewer_api_error"


class GitHubAppConfigurationError(SignalReviewError):
    error = "github_app_configuration_error"


class GitHubWebhookSignatureError(SignalReviewError):
    error = "github_webhook_signature_error"


class GitHubWebhookPayloadError(SignalReviewError):
    error = "github_webhook_payload_error"
