from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    access_token: str | None = Field(default=None, min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    roles: str = Field(default="student", description="Comma-separated roles")
    org_id: str = Field(default="default")


class UserResponse(BaseModel):
    id: str
    email: str
    org_id: str
    roles: str
    is_active: bool
    created_at: str
