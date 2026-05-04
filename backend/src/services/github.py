"""GitHub service helpers."""

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from src.config import get_settings
from src.exceptions.custom import GitHubAPIError, InvalidGitHubURLError, PRNotFoundError

GITHUB_API_BASE_URL = "https://api.github.com"
SAMPLE_PULL_REQUEST_URL = "https://github.com/example/example/pull/123"


@dataclass(frozen=True)
class ParsedPullRequest:
    owner: str
    repo: str
    pull_number: int


@dataclass(frozen=True)
class GitHubPRMetadata:
    title: str
    author: str
    html_url: str
    body: str | None
    base_branch: str
    head_branch: str


@dataclass(frozen=True)
class GitHubChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None


def parse_pr_url(url: str) -> ParsedPullRequest:
    """Parse a GitHub pull request URL into owner, repo, and pull number."""

    parsed_url = urlparse(url.strip())
    if parsed_url.scheme != "https" or parsed_url.netloc != "github.com":
        raise InvalidGitHubURLError(
            "GitHub PR URLs must use https://github.com/{owner}/{repo}/pull/{number}."
        )

    parts = [part for part in parsed_url.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "pull":
        raise InvalidGitHubURLError("Only GitHub pull request URLs are supported.")

    owner, repo, _, pull_number_raw = parts
    if not pull_number_raw.isdigit():
        raise InvalidGitHubURLError("Pull request number must be numeric.")

    return ParsedPullRequest(owner=owner, repo=repo, pull_number=int(pull_number_raw))


async def fetch_pr_metadata(
    owner: str,
    repo: str,
    pull_number: int,
    github_token: str | None = None,
) -> GitHubPRMetadata:
    """Fetch pull request metadata from GitHub."""

    if _is_sample_pull_request(owner=owner, repo=repo, pull_number=pull_number):
        return GitHubPRMetadata(
            title="Add user profile endpoint",
            author="demo-user",
            html_url=SAMPLE_PULL_REQUEST_URL,
            body="Adds an endpoint for fetching a user profile by ID.",
            base_branch="main",
            head_branch="feature/user-profile",
        )

    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=build_github_headers(github_token=github_token))

    payload = _parse_response_json(response, resource_name="pull request")
    if not isinstance(payload, dict):
        raise GitHubAPIError("GitHub returned an unexpected PR metadata payload.")

    user_payload = _read_required_dict(
        payload,
        "user",
        "GitHub PR metadata is missing user details.",
    )
    base_payload = _read_required_dict(
        payload,
        "base",
        "GitHub PR metadata is missing base branch data.",
    )
    head_payload = _read_required_dict(
        payload,
        "head",
        "GitHub PR metadata is missing head branch data.",
    )

    author = _read_required_str(
        user_payload,
        "login",
        "GitHub PR metadata is missing the author login.",
    )
    base_ref = _read_required_str(
        base_payload,
        "ref",
        "GitHub PR metadata is missing the base branch name.",
    )
    head_ref = _read_required_str(
        head_payload,
        "ref",
        "GitHub PR metadata is missing the head branch name.",
    )
    html_url = _read_required_str(payload, "html_url", "GitHub PR metadata is missing html_url.")
    title = _read_required_str(payload, "title", "GitHub PR metadata is missing title.")
    body = payload.get("body")
    if body is not None and not isinstance(body, str):
        raise GitHubAPIError("GitHub PR body was not in the expected format.")

    return GitHubPRMetadata(
        title=title,
        author=author,
        html_url=html_url,
        body=body,
        base_branch=base_ref,
        head_branch=head_ref,
    )


async def fetch_pr_files(
    owner: str,
    repo: str,
    pull_number: int,
    github_token: str | None = None,
) -> list[GitHubChangedFile]:
    """Fetch changed files for a pull request from GitHub."""

    if _is_sample_pull_request(owner=owner, repo=repo, pull_number=pull_number):
        return [
            GitHubChangedFile(
                filename="routes/users.ts",
                status="modified",
                additions=18,
                deletions=1,
                changes=19,
                patch=(
                    "@@ -18,6 +18,23 @@ router.get("
                    "\"/users/:id\", requireAuth, async (req, res) => {\n"
                    "+  const user = await userRepository.findById(req.params.id);\n"
                    "+  if (!user) {\n"
                    "+    return res.status(404).json({ error: \"Not found\" });\n"
                    "+  }\n"
                    "+\n"
                    "+  return res.json(user);\n"
                    " });\n"
                ),
            ),
            GitHubChangedFile(
                filename="routes/users.test.ts",
                status="added",
                additions=8,
                deletions=0,
                changes=8,
                patch=(
                    "@@ -0,0 +1,8 @@\n"
                    "+describe(\"GET /users/:id\", () => {\n"
                    "+  it(\"returns 200 for the owner\", async () => {\n"
                    "+    expect(true).toBe(true);\n"
                    "+  });\n"
                    "+});\n"
                ),
            ),
        ]

    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            headers=build_github_headers(github_token=github_token),
            params={"per_page": 100},
        )

    payload = _parse_response_json(response, resource_name="pull request files")
    if not isinstance(payload, list):
        raise GitHubAPIError("GitHub returned an unexpected files payload.")

    changed_files: list[GitHubChangedFile] = []
    for item in payload:
        if not isinstance(item, dict):
            raise GitHubAPIError("GitHub file payload contained an invalid entry.")
        filename = _read_required_str(
            item,
            "filename",
            "GitHub file metadata was missing filename.",
        )
        status = _read_required_str(
            item,
            "status",
            "GitHub file metadata was missing status.",
        )
        additions = _read_required_int(
            item,
            "additions",
            "GitHub file additions count was invalid.",
        )
        deletions = _read_required_int(
            item,
            "deletions",
            "GitHub file deletions count was invalid.",
        )
        changes = _read_required_int(
            item,
            "changes",
            "GitHub file changes count was invalid.",
        )
        patch = item.get("patch")
        if patch is not None and not isinstance(patch, str):
            raise GitHubAPIError("GitHub file patch was invalid.")
        changed_files.append(
            GitHubChangedFile(
                filename=filename,
                status=status,
                additions=additions,
                deletions=deletions,
                changes=changes,
                patch=patch,
            )
        )

    return changed_files


def build_combined_diff(files: list[GitHubChangedFile]) -> str:
    """Build a single readable diff string from changed files."""

    diff_sections: list[str] = []
    for changed_file in files:
        patch = (
            changed_file.patch
            if changed_file.patch is not None
            else "[No text patch available for this file. File may be binary or too large.]"
        )
        diff_sections.append(
            "\n".join(
                [
                    f"diff --git a/{changed_file.filename} b/{changed_file.filename}",
                    f"File status: {changed_file.status}",
                    f"Additions: {changed_file.additions}, Deletions: {changed_file.deletions}",
                    patch,
                ]
            )
        )
    return "\n\n".join(diff_sections)


def _is_sample_pull_request(*, owner: str, repo: str, pull_number: int) -> bool:
    return owner == "example" and repo == "example" and pull_number == 123


def build_github_headers(github_token: str | None = None) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    auth_token = github_token if github_token is not None else settings.github_token
    if auth_token is not None:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def _parse_response_json(response: httpx.Response, *, resource_name: str) -> object:
    if response.status_code == 404:
        raise PRNotFoundError("Pull request not found or is not publicly accessible.")

    if response.status_code == 403:
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        if rate_limit_remaining == "0":
            raise GitHubAPIError(
                "GitHub API rate limit exceeded. Provide GITHUB_TOKEN to raise limits."
            )
        raise GitHubAPIError("GitHub API request was forbidden. The repository may be private.")

    if response.status_code < 200 or response.status_code >= 300:
        raise GitHubAPIError(
            f"GitHub API returned {response.status_code} while fetching {resource_name}."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise GitHubAPIError(
            f"GitHub API returned malformed JSON while fetching {resource_name}."
        ) from exc


def _read_required_dict(
    payload: dict[str, object],
    key: str,
    error_message: str,
) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise GitHubAPIError(error_message)
    return value


def _read_required_str(payload: dict[str, object], key: str, error_message: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise GitHubAPIError(error_message)
    return value


def _read_required_int(payload: dict[str, object], key: str, error_message: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GitHubAPIError(error_message)
    return value
