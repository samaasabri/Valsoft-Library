from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    picture_url: str = ""
    role: str = Field(default="member")  # "admin" | "member"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    loans: List["Loan"] = Relationship(back_populates="user")


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    author: str = Field(index=True)
    isbn: Optional[str] = Field(default=None, index=True)
    genre: Optional[str] = Field(default=None, index=True)
    published_year: Optional[int] = None
    summary: Optional[str] = None
    tags: Optional[str] = Field(default="")  # comma-separated
    cover_url: Optional[str] = None
    total_copies: int = 1
    available_copies: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

    loans: List["Loan"] = Relationship(back_populates="book")


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    checked_out_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None

    book: Optional[Book] = Relationship(back_populates="loans")
    user: Optional[User] = Relationship(back_populates="loans")
