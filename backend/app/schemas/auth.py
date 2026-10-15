from datetime import datetime
from pydantic import BaseModel


class RegisterTenantRequest(BaseModel):
    company_name: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    tenant_id: int
    email: str
    role: str
    created_at: datetime
