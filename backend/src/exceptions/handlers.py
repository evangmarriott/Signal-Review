"""Global exception handlers."""

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.exceptions.custom import (
    GitHubAPIError,
    GitHubAppConfigurationError,
    GitHubWebhookPayloadError,
    GitHubWebhookSignatureError,
    InvalidGitHubURLError,
    PRNotFoundError,
    ReviewerAPIError,
    SignalReviewError,
)
from src.models.responses import ErrorResponse

ExceptionHandler = Callable[[Request, Exception], JSONResponse]


def _build_error_response(
    *,
    status_code: int,
    error: str,
    detail: str,
) -> JSONResponse:
    payload = ErrorResponse(error=error, detail=detail, status_code=status_code)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _exception_handler_factory(status_code: int) -> ExceptionHandler:
    def handler(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, SignalReviewError):
            return _build_error_response(
                status_code=500,
                error="internal_server_error",
                detail="An unexpected error occurred.",
            )
        return _build_error_response(
            status_code=status_code,
            error=exc.error,
            detail=exc.detail,
        )

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""

    app.add_exception_handler(InvalidGitHubURLError, _exception_handler_factory(422))
    app.add_exception_handler(PRNotFoundError, _exception_handler_factory(404))
    app.add_exception_handler(GitHubAPIError, _exception_handler_factory(502))
    app.add_exception_handler(GitHubAppConfigurationError, _exception_handler_factory(503))
    app.add_exception_handler(GitHubWebhookSignatureError, _exception_handler_factory(401))
    app.add_exception_handler(GitHubWebhookPayloadError, _exception_handler_factory(422))
    app.add_exception_handler(ReviewerAPIError, _exception_handler_factory(503))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        first_error = exc.errors()[0]
        detail = str(first_error.get("msg", "Request validation failed."))
        return _build_error_response(
            status_code=422,
            error="validation_error",
            detail=detail,
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_: Request, __: Exception) -> JSONResponse:
        return _build_error_response(
            status_code=500,
            error="internal_server_error",
            detail="An unexpected error occurred.",
        )
