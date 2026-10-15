from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from sqlmodel import Field, SQLModel


class Letter(SQLModel, table=True):
    __tablename__ = "letter"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    approval_id: int | None = Field(default=None, foreign_key="approval.id", index=True)
    content: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
