# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for fastui_admin.utils."""

from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text

from fastui_admin.utils import (
    _extract_sa_default,
    get_python_type,
    slugify,
    sqlalchemy_to_pydantic,
)

from .conftest import User


class TestGetPythonType:
    def test_integer(self):
        assert get_python_type(Integer()) is int

    def test_string(self):
        assert get_python_type(String(50)) is str

    def test_text(self):
        assert get_python_type(Text()) is str

    def test_boolean(self):
        assert get_python_type(Boolean()) is bool

    def test_float(self):
        assert get_python_type(Float()) is float

    def test_datetime(self):
        assert get_python_type(DateTime()) is datetime

    def test_date(self):
        assert get_python_type(Date()) is date

    def test_unknown_defaults_to_str(self):
        class CustomType:
            pass

        assert get_python_type(CustomType()) is str


class TestSlugify:
    def test_normalizes_spaces_and_case(self):
        assert slugify("  Hello  World  ") == "hello-world"

    def test_strips_punctuation_and_collapses_hyphens(self):
        assert slugify("Hello, world!!! -- test") == "hello-world-test"

    def test_strips_leading_and_trailing_hyphens(self):
        assert slugify("---Hello---") == "hello"

    def test_simple_name(self):
        assert slugify("Audit Logs") == "audit-logs"

    def test_already_slug(self):
        assert slugify("already-good") == "already-good"


class TestSqlalchemyToPydantic:
    def test_creates_pydantic_model(self):
        model = sqlalchemy_to_pydantic(User)
        assert issubclass(model, BaseModel)
        assert "UserSchema" in model.__name__

    def test_includes_all_columns_by_default(self):
        model = sqlalchemy_to_pydantic(User)
        fields = set(model.model_fields.keys())
        assert "id" in fields
        assert "username" in fields
        assert "email" in fields
        assert "is_active" in fields
        assert "created_at" in fields

    def test_include_columns(self):
        model = sqlalchemy_to_pydantic(User, include_columns=["id", "username"])
        fields = set(model.model_fields.keys())
        assert fields == {"id", "username"}

    def test_exclude_columns(self):
        model = sqlalchemy_to_pydantic(User, exclude_columns=["created_at"])
        fields = set(model.model_fields.keys())
        assert "created_at" not in fields

    def test_for_form_excludes_pk(self):
        model = sqlalchemy_to_pydantic(User, for_form=True)
        fields = set(model.model_fields.keys())
        assert "id" not in fields

    def test_from_attributes_config(self):
        model = sqlalchemy_to_pydantic(User)
        assert model.model_config.get("from_attributes") is True


class TestExtractSaDefault:
    def test_column_without_default(self):
        col = Column("test", Integer)
        assert _extract_sa_default(col) is None

    def test_column_with_scalar_default(self):
        col = Column("status", String(20), default="pending")
        assert _extract_sa_default(col) == "pending"

    def test_column_with_callable_default_returns_none(self):
        col = Column("created", DateTime, default=datetime.now)
        assert _extract_sa_default(col) is None

    def test_column_with_boolean_default(self):
        col = Column("active", Boolean, default=True)
        assert _extract_sa_default(col) is True
