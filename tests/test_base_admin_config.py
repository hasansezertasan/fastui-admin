# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for BaseAdmin engine/session_maker validation."""

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastui_admin import BaseAdmin


class TestBaseAdminConfig:
    def test_no_engine_or_session_maker_raises(self) -> None:
        """Constructing BaseAdmin without engine or session_maker raises TypeError."""
        app = FastAPI()
        with pytest.raises(TypeError, match="Neither engine nor session_maker"):
            BaseAdmin(app=app)

    def test_sync_engine_raises(self) -> None:
        """Passing a sync engine raises TypeError."""
        app = FastAPI()
        engine = create_engine("sqlite://")
        with pytest.raises(TypeError, match="Sync engine"):
            BaseAdmin(app=app, engine=engine)

    def test_sync_session_maker_raises(self) -> None:
        """Passing a sync sessionmaker raises TypeError."""
        app = FastAPI()
        engine = create_engine("sqlite://")
        sm = sessionmaker(bind=engine)
        with pytest.raises(TypeError, match="Sync sessionmaker"):
            BaseAdmin(app=app, session_maker=sm)
