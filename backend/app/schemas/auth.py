import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterTenantRequest(BaseModel):
    company_name: str
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip()
        if not EMAIL_PATTERN.match(cleaned):
            raise ValueError("Enter a valid email address")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    tenant_id: int
    email: str
    role: str
    created_at: datetime
