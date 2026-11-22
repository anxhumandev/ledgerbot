"""Structured API errors: every failure returns {"error": {"code", "message", "details", "request_id"}}."""
from __future__ import annotations

import contextvars
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}, "request_id": REQUEST_ID.get()}}


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        token = REQUEST_ID.set(rid)
        try:
            response = await call_next(request)
        finally:
            REQUEST_ID.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = {400: "bad_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
                409: "conflict", 413: "payload_too_large", 422: "invalid_request"}.get(exc.status_code, "error")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("invalid_request", "The request is not valid.", {"fields": fields}), status_code=422)
