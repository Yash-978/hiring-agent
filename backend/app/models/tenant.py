from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class Tenant(SQLModel, table=True):
    __tablename__ = "tenant"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
