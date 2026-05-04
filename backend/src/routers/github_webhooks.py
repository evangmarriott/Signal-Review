"""GitHub App webhook endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Header, Request

from src.services.github_app import (
    PullRequestWebhookContext,
    handle_pull_request_webhook,
    parse_pull_request_webhook,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api/github", tags=["github"])
logger = logging.getLogger(__name__)


async def run_pull_request_webhook_task(context: PullRequestWebhookContext) -> None:
    """Run the webhook task and prevent post-response crashes from unexpected exceptions."""

    try:
        await handle_pull_request_webhook(context)
    except Exception:
        logger.exception(
            "Unhandled GitHub webhook task failure for %s/%s#%s",
            context.owner,
            context.repo,
            context.pull_number,
        )


@router.post("/webhooks")
async def github_webhooks(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(...),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, object]:
    body = await request.body()
    verify_webhook_signature(body=body, signature_header=x_hub_signature_256)

    payload = await request.json()
    if x_github_event == "ping":
        return {"status": "ok", "event": "ping"}
    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    context = parse_pull_request_webhook(payload)
    if context is None:
        return {"status": "ignored", "event": x_github_event}

    background_tasks.add_task(run_pull_request_webhook_task, context)
    return {
        "status": "accepted",
        "event": x_github_event,
        "action": context.action,
        "repository": f"{context.owner}/{context.repo}",
        "pull_number": context.pull_number,
    }
