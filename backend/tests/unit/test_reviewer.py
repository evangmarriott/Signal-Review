import pytest

from src.config import get_settings
from src.exceptions.custom import ReviewerAPIError
from src.models.requests import ReviewFocus
from src.services.github import GitHubPRMetadata
from src.services.reviewer import REPAIR_SYSTEM_PROMPT, SYSTEM_PROMPT, analyze_pr


def _metadata(url: str = "https://github.com/octocat/hello-world/pull/42") -> GitHubPRMetadata:
    return GitHubPRMetadata(
        title="Add user profile endpoint",
        author="demo-user",
        html_url=url,
        body="Body",
        base_branch="main",
        head_branch="feature-branch",
    )


@pytest.mark.asyncio
async def test_mock_response_used_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    result = await analyze_pr(
        metadata=_metadata(url="https://github.com/example/example/pull/123"),
        combined_diff="diff --git a/routes/users.ts b/routes/users.ts",
        repo_context=None,
        focus_areas=[ReviewFocus.SECURITY],
    )

    assert result.overall_risk.value == "high"
    assert result.comments[0].title == "Missing object-level authorization on user lookup"


def test_system_prompt_contains_high_signal_instructions() -> None:
    assert "high-signal code review comments only" in SYSTEM_PROMPT
    assert "Only report issues grounded in the diff or supplied repo context." in SYSTEM_PROMPT
    assert "Return JSON only." in SYSTEM_PROMPT
    assert "Return JSON only." in REPAIR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_malformed_json_raises_reviewer_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def model_dump(self) -> dict[str, object]:
            return {"content": [{"type": "text", "text": "{not valid json"}]}

    class FakeMessages:
        async def create(self, **_: object) -> FakeResponse:
            return FakeResponse()

    class FakeAnthropicClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("src.services.reviewer.AsyncAnthropic", FakeAnthropicClient)
    get_settings.cache_clear()

    with pytest.raises(ReviewerAPIError):
        await analyze_pr(
            metadata=_metadata(url="https://github.com/octocat/private-repo/pull/10"),
            combined_diff="diff --git a/file.ts b/file.ts",
            repo_context=None,
            focus_areas=[ReviewFocus.SECURITY],
        )


@pytest.mark.asyncio
async def test_schema_mismatch_is_repaired(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_messages = None

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self._text = text

        def model_dump(self) -> dict[str, object]:
            return {"content": [{"type": "text", "text": self._text}]}

    class FakeMessages:
        def __init__(self) -> None:
            self.calls = 0

        async def create(self, **_: object) -> FakeResponse:
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(
                    '{"comments":[{"severity":"medium","confidence":"high",'
                    '"category":"logic","problem":"Broken","why_it_matters":"Bad",'
                    '"suggestion":"Fix it"}]}'
                )
            return FakeResponse(
                '{"overall_risk":"medium","merge_recommendation":"comment",'
                '"summary":"Repair pass succeeded.","comments":[{"title":"Recovered title",'
                '"file":"backend/src/services/github_app.py","line":12,'
                '"category":"logic","severity":"medium","confidence":"high",'
                '"problem":"Broken","why_it_matters":"Bad","suggestion":"Fix it"}],'
                '"file_summaries":[{"filename":"backend/src/services/github_app.py",'
                '"change_type":"modified","risk_level":"medium",'
                '"summary":"Recovered summary."}]}'
            )

    class FakeAnthropicClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            nonlocal fake_messages
            fake_messages = FakeMessages()
            self.messages = fake_messages

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("src.services.reviewer.AsyncAnthropic", FakeAnthropicClient)
    get_settings.cache_clear()

    result = await analyze_pr(
        metadata=_metadata(url="https://github.com/octocat/private-repo/pull/10"),
        combined_diff="diff --git a/file.ts b/file.ts",
        repo_context=None,
        focus_areas=[ReviewFocus.SECURITY],
    )

    assert result.summary == "Repair pass succeeded."
    assert result.comments[0].title == "Recovered title"
    assert fake_messages is not None
    assert fake_messages.calls == 2
