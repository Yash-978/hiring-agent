from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas.auth import RegisterTenantRequest, TokenResponse, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register-tenant", response_model=TokenResponse)
def register_tenant(
    data: RegisterTenantRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Register a new company (tenant) and its initial admin user."""
    _, _, token = auth_service.register_tenant(
        session=session,
        company_name=data.company_name,
        email=data.email,
        password=data.password,
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate a user using username (email) and password."""
    _, token = auth_service.authenticate_user(
        session=session,
        email=form_data.username,
        password=form_data.password,
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Retrieve profile of currently authenticated user."""
    assert current_user.id is not None
    role_val = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role)
    )
    return UserRead(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        role=role_val,
        created_at=current_user.created_at,
    )
