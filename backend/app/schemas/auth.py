from pydantic import BaseModel, EmailStr
import uuid

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}