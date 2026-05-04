"""Signal filter service."""

from src.models.requests import ReviewStrictness
from src.models.responses import ReviewComment, ReviewConfidence, ReviewSeverity


def apply_signal_filter(
    comments: list[ReviewComment],
    strictness: ReviewStrictness,
) -> tuple[list[ReviewComment], list[ReviewComment]]:
    """Split review comments into visible and hidden groups based on strictness."""

    visible_comments: list[ReviewComment] = []
    hidden_comments: list[ReviewComment] = []

    for comment in comments:
        if _should_show_comment(comment=comment, strictness=strictness):
            visible_comments.append(comment.model_copy(update={"is_hidden_by_default": False}))
        else:
            hidden_comments.append(comment.model_copy(update={"is_hidden_by_default": True}))

    return visible_comments, hidden_comments


def build_signal_filter_summary(
    visible: list[ReviewComment],
    hidden: list[ReviewComment],
    strictness: ReviewStrictness,
) -> str:
    """Build a one-line summary explaining how Signal Filter classified comments."""

    strictness_label = strictness.value.capitalize()
    visible_phrase = _pluralize(
        count=len(visible),
        singular="high-signal comment",
        plural="high-signal comments",
    )
    hidden_phrase = _pluralize(
        count=len(hidden),
        singular="lower-confidence or lower-severity comment",
        plural="lower-confidence or lower-severity comments",
    )
    return (
        f"{strictness_label} mode showed {len(visible)} {visible_phrase} and hid "
        f"{len(hidden)} {hidden_phrase}."
    )


def _should_show_comment(comment: ReviewComment, strictness: ReviewStrictness) -> bool:
    if strictness == ReviewStrictness.QUIET:
        return comment.severity in {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH} and (
            comment.confidence == ReviewConfidence.HIGH
        )

    if strictness == ReviewStrictness.BALANCED:
        if comment.confidence == ReviewConfidence.LOW or comment.severity == ReviewSeverity.LOW:
            return False
        if comment.severity == ReviewSeverity.MEDIUM:
            return comment.confidence == ReviewConfidence.HIGH
        return comment.confidence in {ReviewConfidence.HIGH, ReviewConfidence.MEDIUM}

    if comment.severity in {
        ReviewSeverity.CRITICAL,
        ReviewSeverity.HIGH,
        ReviewSeverity.MEDIUM,
    }:
        return comment.confidence in {ReviewConfidence.HIGH, ReviewConfidence.MEDIUM}

    return comment.confidence == ReviewConfidence.HIGH


def _pluralize(*, count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural
