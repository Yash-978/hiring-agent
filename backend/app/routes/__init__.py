from app.routes.approvals import router as approvals_router
from app.routes.auth import router as auth_router

__all__ = [
    "auth_router",
    "approvals_router",
]
