# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Shared test fixtures."""

from datetime import datetime, timezone
from typing import AsyncGenerator, ClassVar, List

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastui_admin import BaseAdmin, BaseModelView

# --- Test Models ---


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserAdmin(BaseModelView, model=User):
    name: ClassVar[str] = "Users"
    column_list: ClassVar[List[str]] = ["id", "username", "email", "is_active"]
    page_size: ClassVar[int] = 10


# --- Fixtures ---


@pytest.fixture()
def engine() -> AsyncEngine:
    return create_async_engine("sqlite+aiosqlite://", echo=False)


@pytest.fixture()
def session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture()
async def setup_db(engine: AsyncEngine) -> AsyncGenerator:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
def app(engine: AsyncEngine) -> FastAPI:
    fastapi_app = FastAPI()
    admin = BaseAdmin(app=fastapi_app, engine=engine, title="Test Admin")
    admin.add_view(UserAdmin)
    admin.mount()
    return fastapi_app
