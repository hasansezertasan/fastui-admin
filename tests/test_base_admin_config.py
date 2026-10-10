# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for BaseAdmin engine/session_maker validation."""

import sys

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.applications import Starlette

from fastui_admin import BaseAdmin


class TestBaseAdminConfig:
    """Verify BaseAdmin engine and session_maker validation."""

    @staticmethod
    def test_no_engine_or_session_maker_raises() -> None:
        """Raise TypeError without engine or session_maker."""
        app = FastAPI()
        with pytest.raises(TypeError, match="Neither engine nor session_maker"):
            BaseAdmin(app=app)

    @staticmethod
    def test_sync_engine_raises() -> None:
        """Raise TypeError when a sync engine is given."""
        app = FastAPI()
        engine = create_engine("sqlite://")
        with pytest.raises(TypeError, match="not a supported async engine"):
            BaseAdmin(app=app, engine=engine)  # ty: ignore[invalid-argument-type]

    @staticmethod
    def test_sync_session_maker_raises() -> None:
        """Raise TypeError when a sync sessionmaker is given."""
        app = FastAPI()
        engine = create_engine("sqlite://")
        sm = sessionmaker(bind=engine)
        with pytest.raises(TypeError, match="Sync sessionmaker"):
            BaseAdmin(app=app, session_maker=sm)  # ty: ignore[invalid-argument-type]

    @staticmethod
    def test_unknown_session_maker_type_raises() -> None:
        """Raise TypeError when session_maker has an unknown type."""
        app = FastAPI()
        bad_maker = "not-a-session-maker"
        with pytest.raises(TypeError, match="Unrecognized session_maker type"):
            BaseAdmin(app=app, session_maker=bad_maker)  # ty: ignore

    @staticmethod
    def test_valid_session_maker_accepted() -> None:
        """Accept an explicit async session maker without an engine."""
        app = FastAPI()
        maker = async_sessionmaker(
            create_async_engine("sqlite+aiosqlite://"), expire_on_commit=False
        )
        admin = BaseAdmin(app=app, session_maker=maker, title="Maker Admin")
        assert admin.session_maker is maker

    @staticmethod
    def test_sync_session_maker_raises_without_asyncio(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fall through to the sync check when asyncio support is missing."""
        monkeypatch.setitem(sys.modules, "sqlalchemy.ext.asyncio", None)
        app = FastAPI()
        engine = create_engine("sqlite://")
        sm = sessionmaker(bind=engine)
        with pytest.raises(TypeError, match="Sync sessionmaker"):
            BaseAdmin(app=app, session_maker=sm)  # ty: ignore[invalid-argument-type]

    @staticmethod
    def test_unknown_session_maker_without_imports(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reach the fallback error when neither module imports."""
        monkeypatch.setitem(sys.modules, "sqlalchemy.ext.asyncio", None)
        monkeypatch.setitem(sys.modules, "sqlalchemy.orm", None)
        app = FastAPI()
        with pytest.raises(TypeError, match="Unrecognized session_maker type"):
            BaseAdmin(app=app, session_maker=object())  # ty: ignore[invalid-argument-type]

    @staticmethod
    def test_create_session_maker_without_engine() -> None:
        """Reject a missing engine when building the session maker."""
        with pytest.raises(TypeError, match="no engine provided"):
            BaseAdmin._create_session_maker(None)  # noqa: SLF001

    @staticmethod
    def test_create_session_maker_without_asyncio(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report an unusable engine when asyncio support is missing."""
        monkeypatch.setitem(sys.modules, "sqlalchemy.ext.asyncio", None)
        with pytest.raises(TypeError, match="not a supported async engine"):
            BaseAdmin._create_session_maker(object())  # noqa: SLF001

    @staticmethod
    def test_get_relative_url() -> None:
        """Strip the base URL prefix and handle edge cases."""
        app = FastAPI()
        engine = create_async_engine("sqlite+aiosqlite://")
        admin = BaseAdmin(app=app, engine=engine, title="URL Admin")
        assert admin.get_relative_url("/admin/users") == "/users"
        assert admin.get_relative_url("/other/path") == "/other/path"
        assert admin.get_relative_url("/admin") == "/"

    @staticmethod
    def test_starlette_app_mount() -> None:
        """Mount on a plain Starlette app via route append."""
        app = Starlette()
        engine = create_async_engine("sqlite+aiosqlite://")
        admin = BaseAdmin(app=app, engine=engine, title="Starlette Admin")
        admin.mount()
        assert any(getattr(route, "path", "") == "/admin" for route in app.routes)
