from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=70)

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_role: UserRole

class GoogleLoginRequest(BaseModel):
    token: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True  # Allows Pydantic to read SQLAlchemy models