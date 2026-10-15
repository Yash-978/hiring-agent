import os
from collections.abc import Generator
from typing import Any
# pyrefly: ignore [missing-import]
import pytest
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from sqlmodel import Session, SQLModel, create_engine
# pyrefly: ignore [missing-import]
from sqlmodel.pool import StaticPool    

# Ensure tests run against in-memory SQLite
os.environ["DATABASE_URL"] = "sqlite://"        
os.environ["LLM_PROVIDER"] = "fake"

from app.config import get_settings
get_settings.cache_clear()

from app.db import get_session
from app.main import app
from app.models import Tenant, User, UserRole
from app.services import auth_service


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override() -> Session:
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def create_authenticated_tenant(
    session: Session,
    company_name: str,
    email: str,
    password: str = "password123",
) -> dict[str, Any]:
    """Helper that creates a tenant and its admin user, returning objects and auth headers."""
    tenant, user, token = auth_service.register_tenant(
        session=session,
        company_name=company_name,
        email=email,
        password=password,
    )
    return {
        "tenant": tenant,
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def create_tenant_user(
    session: Session,
    tenant_id: int,
    email: str,
    role: UserRole = UserRole.MEMBER,
    password: str = "password123",
) -> dict[str, Any]:
    """Helper that creates a user with a given role in a tenant, returning user and auth headers."""
    user = User(
        tenant_id=tenant_id,
        email=email.strip().lower(),
        hashed_password=auth_service.hash_password(password),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    role_val = role.value if isinstance(role, UserRole) else str(role)
    token = auth_service.create_access_token(user.id, tenant_id, role_val)
    return {
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture(name="two_tenants")
def two_tenants_fixture(session: Session) -> dict[str, dict[str, Any]]:
    """Tenant isolation infrastructure fixture: creates two distinct tenants with auth headers."""
    tenant_a_data = create_authenticated_tenant(
        session=session,
        company_name="Tenant Alpha",
        email="admin@alpha.com",
        password="alpha_password_123",
    )
    tenant_b_data = create_authenticated_tenant(
        session=session,
        company_name="Tenant Beta",
        email="admin@beta.com",
        password="beta_password_123",
    )
    return {
        "tenant_a": tenant_a_data,
        "tenant_b": tenant_b_data,
    }
