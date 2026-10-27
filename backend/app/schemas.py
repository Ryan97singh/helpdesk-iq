from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role, TicketStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: Role
    auth_provider: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentOut(ORM):
    id: int
    title: str
    filename: str
    status: str
    chunk_count: int
    created_at: datetime


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class TicketIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)


class TicketUpdate(BaseModel):
    status: TicketStatus


class TicketOut(ORM):
    id: int
    title: str
    description: str
    status: TicketStatus
    category: str | None
    priority: str | None
    suggested_reply: str | None
    triage_status: str
    created_by: int
    created_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
