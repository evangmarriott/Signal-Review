from src.models.requests import ReviewStrictness
from src.models.responses import ReviewCategory, ReviewComment, ReviewConfidence, ReviewSeverity
from src.services.signal_filter import apply_signal_filter, build_signal_filter_summary


def _comment(
    *,
    severity: ReviewSeverity,
    confidence: ReviewConfidence,
) -> ReviewComment:
    return ReviewComment(
        title=f"{severity.value}-{confidence.value}",
        file="routes/users.ts",
        line=10,
        category=ReviewCategory.LOGIC,
        severity=severity,
        confidence=confidence,
        problem="Problem",
        why_it_matters="Why it matters",
        suggestion="Suggested fix",
    )


def test_quiet_mode_shows_only_high_or_critical_with_high_confidence() -> None:
    comments = [
        _comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.CRITICAL, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.MEDIUM, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.MEDIUM),
    ]

    visible, hidden = apply_signal_filter(comments, ReviewStrictness.QUIET)

    assert len(visible) == 2
    assert len(hidden) == 2


def test_balanced_mode_hides_low_severity_and_low_confidence() -> None:
    comments = [
        _comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.MEDIUM),
        _comment(severity=ReviewSeverity.MEDIUM, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.LOW, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.LOW),
    ]

    visible, hidden = apply_signal_filter(comments, ReviewStrictness.BALANCED)

    assert [comment.title for comment in visible] == ["high-medium", "medium-high"]
    assert len(hidden) == 2


def test_strict_mode_shows_medium_and_high_and_hides_only_weakest_low_confidence_lows() -> None:
    comments = [
        _comment(severity=ReviewSeverity.MEDIUM, confidence=ReviewConfidence.MEDIUM),
        _comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.MEDIUM),
        _comment(severity=ReviewSeverity.LOW, confidence=ReviewConfidence.HIGH),
        _comment(severity=ReviewSeverity.LOW, confidence=ReviewConfidence.LOW),
    ]

    visible, hidden = apply_signal_filter(comments, ReviewStrictness.STRICT)

    assert [comment.title for comment in visible] == ["medium-medium", "high-medium", "low-high"]
    assert [comment.title for comment in hidden] == ["low-low"]


def test_hidden_comments_get_is_hidden_by_default_true() -> None:
    visible, hidden = apply_signal_filter(
        [_comment(severity=ReviewSeverity.LOW, confidence=ReviewConfidence.LOW)],
        ReviewStrictness.BALANCED,
    )

    assert not visible
    assert hidden[0].is_hidden_by_default is True


def test_visible_comments_get_is_hidden_by_default_false() -> None:
    visible, hidden = apply_signal_filter(
        [_comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.HIGH)],
        ReviewStrictness.BALANCED,
    )

    assert not hidden
    assert visible[0].is_hidden_by_default is False


def test_summary_includes_visible_and_hidden_counts() -> None:
    visible = [_comment(severity=ReviewSeverity.HIGH, confidence=ReviewConfidence.HIGH)]
    hidden = [_comment(severity=ReviewSeverity.LOW, confidence=ReviewConfidence.LOW)]

    summary = build_signal_filter_summary(visible, hidden, ReviewStrictness.BALANCED)

    expected_summary = (
        "Balanced mode showed 1 high-signal comment and hid 1 lower-confidence or "
        "lower-severity comment."
    )

    assert expected_summary == summary
