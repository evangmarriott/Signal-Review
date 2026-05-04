from src.exceptions.custom import InvalidGitHubURLError
from src.services.github import GitHubChangedFile, build_combined_diff, parse_pr_url


def test_parse_pr_url_valid_returns_owner_repo_and_number() -> None:
    parsed = parse_pr_url("https://github.com/octocat/hello-world/pull/42")

    assert parsed.owner == "octocat"
    assert parsed.repo == "hello-world"
    assert parsed.pull_number == 42


def test_parse_pr_url_invalid_url_raises_invalid_github_url_error() -> None:
    try:
        parse_pr_url("https://gitlab.com/octocat/hello-world/merge_requests/42")
    except InvalidGitHubURLError:
        return

    raise AssertionError("Expected InvalidGitHubURLError to be raised.")


def test_parse_pr_url_issue_url_raises_invalid_github_url_error() -> None:
    try:
        parse_pr_url("https://github.com/octocat/hello-world/issues/42")
    except InvalidGitHubURLError:
        return

    raise AssertionError("Expected InvalidGitHubURLError to be raised.")


def test_build_combined_diff_includes_filename_and_patch() -> None:
    diff = build_combined_diff(
        [
            GitHubChangedFile(
                filename="src/app.ts",
                status="modified",
                additions=3,
                deletions=1,
                changes=4,
                patch="@@ -1 +1 @@\n-console.log('old')\n+console.log('new')",
            )
        ]
    )

    assert "diff --git a/src/app.ts b/src/app.ts" in diff
    assert "File status: modified" in diff
    assert "+console.log('new')" in diff


def test_build_combined_diff_handles_missing_patch() -> None:
    diff = build_combined_diff(
        [
            GitHubChangedFile(
                filename="assets/logo.png",
                status="modified",
                additions=0,
                deletions=0,
                changes=0,
                patch=None,
            )
        ]
    )

    assert "[No text patch available for this file. File may be binary or too large.]" in diff
