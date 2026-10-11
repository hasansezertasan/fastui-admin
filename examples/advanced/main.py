# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""
Advanced FastUI Admin example.

Custom session maker, excluded columns, a custom stats page, and view
categories.

Run with:
    uvicorn examples.advanced.main:app --reload --port 5000

Then visit:
    http://localhost:5000/backend/
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

from fastapi import FastAPI
from fastui import components as c
from sqlalchemy import ForeignKey, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing_extensions import override

from fastui_admin import BaseAdmin, BaseModelView, BaseView

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

# --- Database Models ---


class Base(DeclarativeBase):
    """Base class for all models."""


class Author(Base):
    """Author model."""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)

    books: Mapped[list[Book]] = relationship(back_populates="author")


class Book(Base):
    """Book model."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    isbn: Mapped[str] = mapped_column(String(20), unique=True)
    internal_notes: Mapped[str] = mapped_column(String(500), default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))

    author: Mapped[Author] = relationship(back_populates="books")


# --- Database Setup (explicit session maker) ---

DATABASE_URL = "sqlite+aiosqlite:///./advanced.db"
engine = create_async_engine(DATABASE_URL, echo=True)
session_maker = async_sessionmaker(engine, class_=AsyncSession)


async def init_db() -> None:
    """Create database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- Admin Views ---


class AuthorAdmin(BaseModelView, model=Author):
    """Admin view for Author model."""

    name: ClassVar[str] = "Authors"
    category: ClassVar[str | None] = "Catalog"
    column_list: ClassVar[list[str]] = ["id", "name", "email"]
    page_size: ClassVar[int] = 10


class BookAdmin(BaseModelView, model=Book):
    """Admin view for Book model (internal notes hidden from the list)."""

    name: ClassVar[str] = "Books"
    category: ClassVar[str | None] = "Catalog"
    column_exclude_list: ClassVar[list[str]] = ["internal_notes"]
    page_size: ClassVar[int] = 10


class StatsView(BaseView):
    """Custom stats page showing catalog totals."""

    name: ClassVar[str] = "Stats"
    category: ClassVar[str | None] = "Catalog"
    icon: ClassVar[str | None] = "chart"

    @override
    async def render(self, _request: Request) -> list[c.AnyComponent]:
        """Render catalog totals.

        Returns:
            List of FastUI components.
        """
        async with self._admin.session_maker() as session:
            author_count = await session.scalar(
                select(func.count()).select_from(Author)
            )
            book_count = await session.scalar(select(func.count()).select_from(Book))

        return self._admin.layout.render(
            c.Heading(text="Catalog Stats", level=2),
            c.Paragraph(text=f"Authors: {author_count or 0}"),
            c.Paragraph(text=f"Books: {book_count or 0}"),
        )


# --- FastAPI App ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(title="Advanced FastUI Admin Example", lifespan=lifespan)


# --- Admin Setup ---

admin = BaseAdmin(
    app=app,
    session_maker=session_maker,
    title="Advanced Admin",
    base_url="/backend",
    logo_url="https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
)

admin.add_view(AuthorAdmin)
admin.add_view(BookAdmin)
admin.add_view(StatsView)
admin.mount()


# --- Seed Data Endpoint ---


@app.post("/seed")
async def seed_data() -> dict[str, str]:
    """Seed database with sample data.

    Returns:
        Status message dictionary.
    """
    async with session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(Author))
        if result.first():
            return {"message": "Data already exists"}

        # Create sample authors
        authors = [
            Author(name="Ada Lovelace", email="ada@example.com"),
            Author(name="Alan Turing", email="alan@example.com"),
        ]
        session.add_all(authors)
        await session.commit()

        # Refresh to get IDs
        for author in authors:
            await session.refresh(author)

        # Create sample books
        books = [
            Book(
                title="Notes on the Analytical Engine",
                isbn="978-0-00-000001-1",
                internal_notes="First edition scan pending.",
                author_id=authors[0].id,
            ),
            Book(
                title="Computing Machinery and Intelligence",
                isbn="978-0-00-000002-2",
                internal_notes="Mind paper, 1950.",
                author_id=authors[1].id,
            ),
        ]
        session.add_all(books)
        await session.commit()

    return {"message": "Seed data created successfully"}


# --- Root Redirect ---


@app.get("/")
async def root() -> dict[str, str]:
    """Redirect info for root path.

    Returns:
        Welcome message with admin and seed URLs.
    """
    return {
        "message": "Welcome! Visit /backend/ for the admin interface.",
        "admin_url": "/backend/",
        "seed_url": "/seed (POST)",
    }
