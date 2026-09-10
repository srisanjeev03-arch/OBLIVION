"""FastAPI application factory and route registration."""
import os

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from oblivion.api.routes import (
    auth_router,
    certificates_router,
    evidence_router,
    operations_router,
    pipeline_router,
    recovery_router,
    targets_router,
)


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application."""
    app = FastAPI(
        title="Oblivion API",
        version="0.1.0",
        description="Backend API for controlled data erasure, recovery, residual analysis, assurance and certificate verification.",
    )

    # CORS configuration - restricted origins, no wildcard with credentials
    cors_origins = os.environ.get("OBLIVION_CORS_ORIGINS", "http://localhost:3000")
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Exception Handlers ensuring consistent ErrorResponse
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            content = exc.detail
        else:
            content = {"error_code": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request payload validation failed",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak raw stack traces or internal secrets
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during operation processing",
            },
        )

    # Register Routers
    app.include_router(auth_router)
    app.include_router(targets_router)
    app.include_router(operations_router)
    app.include_router(pipeline_router)
    app.include_router(recovery_router)
    app.include_router(certificates_router)
    app.include_router(evidence_router)


    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "service": "oblivion"}

    return app


app = create_app()
