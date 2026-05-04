"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.exceptions.handlers import register_exception_handlers
from src.routers.github_webhooks import router as github_webhook_router
from src.routers.review import router as review_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title="SignalReview API",
        version=settings.app_version,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(review_router)
    app.include_router(github_webhook_router)
    register_exception_handlers(app)
    return app


app = create_app()
