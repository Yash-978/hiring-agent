from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from fastapi import HTTPException, status
import jwt
from sqlmodel import Session, select

from app.config import get_settings
from app.models import AuditActorType, Tenant, User, UserRole
from app.services.audit_service import log_event


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hashed password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: int, tenant_id: int, role: str) -> str:
    """Create a PyJWT access token with HS256, 8-hour expiry, and user/tenant claims."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=8)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a PyJWT access token."""
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


def register_tenant(
    session: Session,
    company_name: str,
    email: str,
    password: str,
) -> tuple[Tenant, User, str]:
    """Create a new Tenant and its first admin user, writing an audit log entry."""
    cleaned_email = email.strip().lower()
    existing_user = session.exec(
        select(User).where(User.email == cleaned_email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    tenant = Tenant(name=company_name)
    session.add(tenant)
    session.flush()

    assert tenant.id is not None
    user = User(
        tenant_id=tenant.id,
        email=cleaned_email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.flush()

    assert user.id is not None
    log_event(
        session=session,
        tenant_id=tenant.id,
        actor_type=AuditActorType.USER,
        actor_name=user.email,
        action="register_tenant",
        entity_type="tenant",
        entity_id=tenant.id,
        details={"company_name": company_name, "email": cleaned_email},
    )

    session.commit()
    session.refresh(tenant)
    session.refresh(user)

    role_val = (
        user.role.value if isinstance(user.role, UserRole) else str(user.role)
    )
    token = create_access_token(user.id, tenant.id, role_val)
    return tenant, user, token


def authenticate_user(
    session: Session,
    email: str,
    password: str,
) -> tuple[User, str]:
    """Authenticate a user across tenants by email, writing an audit log entry."""
    cleaned_email = email.strip().lower()
    user = session.exec(
        select(User).where(User.email == cleaned_email)
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    assert user.id is not None
    log_event(
        session=session,
        tenant_id=user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=user.email,
        action="login",
        entity_type="user",
        entity_id=user.id,
        details={"email": user.email},
    )
    session.commit()
    session.refresh(user)

    role_val = (
        user.role.value if isinstance(user.role, UserRole) else str(user.role)
    )
    token = create_access_token(user.id, user.tenant_id, role_val)
    return user, token
