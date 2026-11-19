from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .db import Base, engine
from . import models  # noqa: F401
from .routers import alerts, auth, cells, events, ingest, reports
from .db import get_db
from .deps import require_role
from .services.audit import verify_audit_chain


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _protect_audit_table()
    yield


def _protect_audit_table():
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log "
                "BEGIN SELECT RAISE(ABORT, 'audit_log is insert-only'); END"
            )
            connection.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log "
                "BEGIN SELECT RAISE(ABORT, 'audit_log is insert-only'); END"
            )
        elif connection.dialect.name == "postgresql":
            connection.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION liveslide_reject_audit_mutation() RETURNS trigger AS $$
                BEGIN RAISE EXCEPTION 'audit_log is insert-only'; END; $$ LANGUAGE plpgsql
            """)
            connection.exec_driver_sql("DROP TRIGGER IF EXISTS audit_no_mutation ON audit_log")
            connection.exec_driver_sql("""
                CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_log
                FOR EACH ROW EXECUTE FUNCTION liveslide_reject_audit_mutation()
            """)


app = FastAPI(title="Liveslide API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cells.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        error = detail
    else:
        error = {"code": "http_error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error",
                           "message": "Request validation failed",
                           "details": [{"loc": item.get("loc"), "msg": item.get("msg"),
                                        "type": item.get("type")} for item in exc.errors()]}})


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/api/v1/audit/verify", tags=["audit"])
def audit_verify(db=Depends(get_db), user=Depends(require_role("officer", "admin"))):
    return verify_audit_chain(db)
