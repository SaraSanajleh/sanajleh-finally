"""Global exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    LLMError,
    LLMResponseParseError,
    PackageGenerationBusyError,
    PackageGenerationError,
    ReTourError,
    ValidationError,
)
from app.schemas.response.package_response import ErrorDetail, ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized error handlers on the FastAPI application."""

    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details)
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            f"{'.'.join(str(loc) for loc in e['loc'] if loc != 'body')}: {e['msg']}"
            for e in exc.errors()
        ]
        body = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed",
                details=details,
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_error(_: Request, exc: PydanticValidationError) -> JSONResponse:
        details = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()]
        body = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed",
                details=details,
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(LLMError)
    async def handle_llm_error(_: Request, exc: LLMError) -> JSONResponse:
        status = 504 if exc.code == "llm_error" and "timed out" in exc.message.lower() else 502
        body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=status, content=body.model_dump())

    @app.exception_handler(LLMResponseParseError)
    async def handle_parse_error(_: Request, exc: LLMResponseParseError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=502, content=body.model_dump())

    @app.exception_handler(PackageGenerationBusyError)
    async def handle_generation_busy(_: Request, exc: PackageGenerationBusyError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=409, content=body.model_dump())

    @app.exception_handler(PackageGenerationError)
    async def handle_generation_error(_: Request, exc: PackageGenerationError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=500, content=body.model_dump())

    @app.exception_handler(ReTourError)
    async def handle_retour_error(_: Request, exc: ReTourError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=500, content=body.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(code="internal_error", message="An unexpected error occurred")
        )
        return JSONResponse(status_code=500, content=body.model_dump())
