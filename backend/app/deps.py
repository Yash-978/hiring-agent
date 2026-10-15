from collections.abc import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlmodel import Session

from app.db import get_session
from app.models import User, UserRole
from app.services.auth_service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Dependency that extracts, decodes and validates the current user token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if sub is None or tenant_id is None:
            raise credentials_exception
        user_id = int(sub)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exception

    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception
    if user.tenant_id != tenant_id:
        raise credentials_exception

    return user


def require_role(*roles: str | UserRole) -> Callable[[User], User]:
    """Dependency factory that verifies the current user has one of the allowed roles."""
    allowed_roles = {
        r.value if isinstance(r, UserRole) else str(r) for r in roles
    }

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_checker
