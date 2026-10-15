"""Pytest configuration shared across the test suite.

Auto-applies a per-component marker to each test based on its top-level
``tests/<dir>/`` directory, so ``pytest -m web`` (or ``-m "not web"``) selects a
component without per-test decoration. Markers are registered in pyproject.toml
``[tool.pytest.ini_options] markers``. See issue #160 / https://hasansezertasan.github.io/copier-pyproject/context/ci-topology/#per-component-markers-path-filtered-jobs-and-one-coverage-gate-per-component.

Also keeps the Markdown doctest surface to the single root ``README.md``: see
``collect_ignore_glob`` below.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastui_admin import BaseAdmin, BaseModelView

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ``--doctest-glob=README.md`` (pyproject ``addopts``) matches on the *basename*,
# so without this every ``tests/**/README.md`` -- fixture notes, a subdirectory
# guide -- would also be collected as a doctest the moment it contained a ``>>>``
# line. The root README is the whole Markdown doctest surface (https://hasansezertasan.github.io/copier-pyproject/context/docs-stack/#documentation-code-examples-are-executed-not-pasted);
# prose
# under tests/ stays prose.
collect_ignore_glob = ["*.md"]


# tests/<dir> names that map to a component marker, rendered from the enabled
# components. An unmarked dir (e.g. a future one) is simply left unmarked.
# `# fmt: off` keeps this one-per-line no matter how many components are enabled:
# the generated ruff config sets skip-magic-trailing-comma, so an unguarded set
# literal would otherwise collapse or explode purely by line width.
# fmt: off
_COMPONENT_DIRS: frozenset[str] = frozenset({
    "core",
})
# fmt: on


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark each collected test with its top-level tests/<dir> component name."""
    tests_root = Path(str(config.rootpath)) / "tests"
    for item in items:
        try:
            rel = item.path.relative_to(tests_root)
        except ValueError:  # pragma: no cover - defensive: items are under tests/
            continue
        component = rel.parts[0] if len(rel.parts) > 1 else "core"
        if component in _COMPONENT_DIRS:
            item.add_marker(component)


# --- Project fixtures (preserved from pre-template suite) ---


class Base(DeclarativeBase):
    """Declarative base for test models."""


class User(Base):
    """Test user model used by admin fixtures."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class UserAdmin(BaseModelView, model=User):
    """Test admin view for the user model."""

    name: ClassVar[str] = "Users"
    column_list: ClassVar[list[str]] = ["id", "username", "email", "is_active"]
    page_size: ClassVar[int] = 10


@pytest.fixture
def engine() -> AsyncEngine:
    """Provide an async SQLite engine for tests."""
    return create_async_engine("sqlite+aiosqlite://", echo=False)


@pytest.fixture
def session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Provide an async session factory bound to the engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def setup_db(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Create tables before a test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app(engine: AsyncEngine) -> FastAPI:
    """Build a FastAPI app with the test admin mounted."""
    fastapi_app = FastAPI()
    admin = BaseAdmin(app=fastapi_app, engine=engine, title="Test Admin")
    admin.add_view(UserAdmin)
    admin.mount()
    return fastapi_app
