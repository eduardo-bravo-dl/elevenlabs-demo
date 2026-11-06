import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import db
from app.config import Settings, load_settings
from app.routes import public, tools

log = logging.getLogger("pms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"level": record.levelname.lower(), "logger": record.name,
                 "msg": record.getMessage()}
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry)


def configure_logging() -> None:
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging()

    conn = db.connect(settings.db_path)
    db.init_schema(conn)
    conn.close()

    app = FastAPI(title="Hotel Casa Jacaranda mock PMS", version="1.0.0")
    app.state.settings = settings
    app.include_router(public)
    app.include_router(tools)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            log.info("request", extra={"fields": {
                "method": request.method,
                "endpoint": request.url.path,
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }})

    @app.exception_handler(RequestValidationError)
    async def short_validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        message = first.get("msg", "Invalid request.").removeprefix("Value error, ")
        return JSONResponse(status_code=422, content={
            "error": "invalid_request",
            "message": f"{field}: {message}" if field else message,
        })

    return app
