# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""
Basic FastUI Admin example with User and Post models.

Run with:
    uvicorn examples.basic.main:app --reload --port 5000

Then visit:
    http://localhost:5000/admin/
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import ClassVar, List

from fastapi import FastAPI
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from fastui_admin import BaseAdmin, BaseModelView

# --- Database Models ---


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    posts: Mapped[List["Post"]] = relationship(back_populates="author")


class Post(Base):
    """Post model."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    author: Mapped[User] = relationship(back_populates="posts")


# --- Database Setup ---

DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"
engine = create_async_engine(DATABASE_URL, echo=True)


async def init_db() -> None:
    """Create database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- Admin Views ---


class UserAdmin(BaseModelView, model=User):
    """Admin view for User model."""

    name: ClassVar[str] = "Users"
    column_list: ClassVar[List[str]] = ["id", "username", "email", "is_active", "created_at"]
    page_size: ClassVar[int] = 25


class PostAdmin(BaseModelView, model=Post):
    """Admin view for Post model."""

    name: ClassVar[str] = "Posts"
    column_list: ClassVar[List[str]] = ["id", "title", "published", "author_id", "created_at"]
    page_size: ClassVar[int] = 25


# --- FastAPI App ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(title="FastUI Admin Example", lifespan=lifespan)


# --- Admin Setup ---

admin = BaseAdmin(
    app=app,
    engine=engine,
    title="My Admin",
    base_url="/admin",
)

admin.add_view(UserAdmin)
admin.add_view(PostAdmin)
admin.mount()


# --- Seed Data Endpoint ---


@app.post("/seed")
async def seed_data() -> dict[str, str]:
    """Seed database with sample data."""
    session_maker = async_sessionmaker(engine, class_=AsyncSession)
    async with session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(User))
        if result.first():
            return {"message": "Data already exists"}

        # Create sample users
        users = [
            User(username="alice", email="alice@example.com", is_active=True),
            User(username="bob", email="bob@example.com", is_active=True),
            User(username="charlie", email="charlie@example.com", is_active=False),
        ]
        session.add_all(users)
        await session.commit()

        # Refresh to get IDs
        for user in users:
            await session.refresh(user)

        # Create sample posts
        posts = [
            Post(
                title="Hello World",
                content="My first post!",
                author_id=users[0].id,
                published=True,
            ),
            Post(
                title="Learning FastUI",
                content="FastUI is great for building UIs with Python.",
                author_id=users[0].id,
                published=True,
            ),
            Post(
                title="Draft Post",
                content="This is a draft that hasn't been published yet.",
                author_id=users[1].id,
                published=False,
            ),
        ]
        session.add_all(posts)
        await session.commit()

    return {"message": "Seed data created successfully"}


# --- Root Redirect ---


@app.get("/")
async def root() -> dict[str, str]:
    """Redirect info for root path."""
    return {
        "message": "Welcome! Visit /admin/ for the admin interface.",
        "admin_url": "/admin/",
        "seed_url": "/seed (POST)",
    }
