from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import create_db_and_tables
from app.exceptions import (
    ApprovalRequiredException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
import app.models  # noqa: F401
from app.routes.approvals import router as approvals_router
from app.routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    yield


app = FastAPI(
    title="Hiring Agent API",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(approvals_router)


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message or "Not Found"})


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message or "Forbidden"})


@app.exception_handler(ConflictException)
async def conflict_handler(request: Request, exc: ConflictException) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message or "Conflict"})


@app.exception_handler(ApprovalRequiredException)
async def approval_required_handler(
    request: Request, exc: ApprovalRequiredException
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message or "Approval required"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
