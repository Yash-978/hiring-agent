from app.routes.applications import router as applications_router
from app.routes.approvals import router as approvals_router
from app.routes.auth import router as auth_router
from app.routes.candidates import router as candidates_router
from app.routes.jobs import router as jobs_router

__all__ = [
    "auth_router",
    "approvals_router",
    "jobs_router",
    "candidates_router",
    "applications_router",
]
