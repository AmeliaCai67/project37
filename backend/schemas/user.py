from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from models.user import Role


# ============== Token ==============
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# ============== User ==============
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[Role] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    role: Role
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserInDB(UserBase):
    id: int
    hashed_password: str
    role: Role
    is_active: bool
    
    class Config:
        from_attributes = True
