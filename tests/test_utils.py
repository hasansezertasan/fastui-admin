# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for fastui_admin.utils."""

from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text

from fastui_admin.utils import (
    get_model_columns,
    get_pk_column,
    get_python_type,
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
        # Unknown SA type falls back to str
        class CustomType:
            pass

        assert get_python_type(CustomType()) is str


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


class TestGetPkColumn:
    def test_returns_pk_name(self):
        assert get_pk_column(User) == "id"


class TestGetModelColumns:
    def test_returns_all_columns(self):
        cols = get_model_columns(User)
        assert "id" in cols
        assert "username" in cols
        assert "email" in cols
