from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "admin"
    APPROVER = "approver"
    MEMBER = "member"


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    email: str = Field(index=True)
    hashed_password: str
    role: UserRole = Field(
        default=UserRole.MEMBER,
        sa_column=Column(String, nullable=False, default=UserRole.MEMBER.value),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
