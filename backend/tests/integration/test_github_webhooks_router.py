import hashlib
import hmac
import json
from collections.abc import Mapping

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from src.main import create_app
from src.services.github_app import PullRequestWebhookContext


def test_post_github_webhooks_ping_returns_ok(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    client = TestClient(create_app())
    payload = {"zen": "Keep it logically awesome."}

    response = client.post(
        "/api/github/webhooks",
        content=json.dumps(payload).encode("utf-8"),
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _build_signature(payload, "test-secret"),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "event": "ping"}


def test_post_github_webhooks_pull_request_accepted(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    client = TestClient(create_app())
    captured_context: list[PullRequestWebhookContext] = []

    async def fake_handle_pull_request_webhook(context: PullRequestWebhookContext) -> None:
        captured_context.append(context)

    monkeypatch.setattr(
        "src.routers.github_webhooks.handle_pull_request_webhook",
        fake_handle_pull_request_webhook,
    )

    payload = {
        "action": "opened",
        "installation": {"id": 12345},
        "repository": {"name": "hello-world", "owner": {"login": "octocat"}},
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/octocat/hello-world/pull/42",
            "head": {"sha": "abc123"},
        },
    }

    response = client.post(
        "/api/github/webhooks",
        content=json.dumps(payload).encode("utf-8"),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _build_signature(payload, "test-secret"),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "event": "pull_request",
        "action": "opened",
        "repository": "octocat/hello-world",
        "pull_number": 42,
    }
    assert captured_context == [
        PullRequestWebhookContext(
            action="opened",
            installation_id=12345,
            owner="octocat",
            repo="hello-world",
            pull_number=42,
            head_sha="abc123",
            pr_url="https://github.com/octocat/hello-world/pull/42",
        )
    ]


def test_post_github_webhooks_invalid_signature_returns_401(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    client = TestClient(create_app())

    response = client.post(
        "/api/github/webhooks",
        content=b"{}",
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": "sha256=invalid",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == "github_webhook_signature_error"


def _build_signature(payload: Mapping[str, object], secret: str) -> str:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
