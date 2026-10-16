from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.services.job_service import ensure_job_unique_index


from app.exceptions import (
    ApprovalRequiredException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
import app.models  # noqa: F401
from app.routes.applications import router as applications_router
from app.routes.approvals import router as approvals_router
from app.routes.auth import router as auth_router
from app.routes.candidates import router as candidates_router
from app.routes.jobs import router as jobs_router
from app.routes.letters import router as letters_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    ensure_job_unique_index(engine)
    yield


app = FastAPI(
    title="Hiring Agent API",
    lifespan=lifespan,
)

from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

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
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(letters_router)


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message or "Not Found"})


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message or "Forbidden"})


@app.exception_handler(ConflictException)
async def conflict_handler(request: Request, exc: ConflictException) -> JSONResponse:
    content: dict[str, object] = {"detail": exc.message or "Conflict"}
    content.update(exc.payload)
    return JSONResponse(status_code=409, content=content)


@app.exception_handler(ApprovalRequiredException)
async def approval_required_handler(
    request: Request, exc: ApprovalRequiredException
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message or "Approval required"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict[str, object]:
    """Describe the active LLM provider so the UI can show demo mode."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER
    model = settings.GEMINI_MODEL if provider == "gemini" else "fake"
    return {
        "llm_provider": provider,
        "llm_model": model,
        "demo_mode": provider == "fake",
    }
