# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for fastui_admin.utils."""

from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    Sequence,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeEngine

from fastui_admin.utils import (
    _extract_sa_default,
    get_python_type,
    slugify,
    sqlalchemy_to_pydantic,
)

from .conftest import Base, User


class NullableWidget(Base):
    """Sample model with a nullable column."""

    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str | None] = mapped_column(String(50))


class TestGetPythonType:
    """Verify get_python_type mappings."""

    @staticmethod
    def test_integer() -> None:
        """Verify integer maps to int."""
        assert get_python_type(Integer()) is int

    @staticmethod
    def test_string() -> None:
        """Verify string maps to str."""
        assert get_python_type(String(50)) is str

    @staticmethod
    def test_text() -> None:
        """Verify text maps to str."""
        assert get_python_type(Text()) is str

    @staticmethod
    def test_boolean() -> None:
        """Verify boolean maps to bool."""
        assert get_python_type(Boolean()) is bool

    @staticmethod
    def test_float() -> None:
        """Verify float maps to float."""
        assert get_python_type(Float()) is float

    @staticmethod
    def test_datetime() -> None:
        """Verify datetime maps to datetime."""
        assert get_python_type(DateTime()) is datetime

    @staticmethod
    def test_date() -> None:
        """Verify date maps to date."""
        assert get_python_type(Date()) is date

    @staticmethod
    def test_unknown_defaults_to_str() -> None:
        """Verify unknown types default to str."""

        class CustomType(TypeEngine):
            """Unmapped SQLAlchemy type for fallback coverage."""

        assert get_python_type(CustomType()) is str


class TestSlugify:
    """Verify slugify normalization."""

    @staticmethod
    def test_normalizes_spaces_and_case() -> None:
        """Verify spaces collapse and case folds."""
        assert slugify("  Hello  World  ") == "hello-world"

    @staticmethod
    def test_strips_punctuation_and_collapses_hyphens() -> None:
        """Verify punctuation strips and hyphens collapse."""
        assert slugify("Hello, world!!! -- test") == "hello-world-test"

    @staticmethod
    def test_strips_leading_and_trailing_hyphens() -> None:
        """Verify leading and trailing hyphens strip."""
        assert slugify("---Hello---") == "hello"

    @staticmethod
    def test_simple_name() -> None:
        """Verify a simple name slugifies."""
        assert slugify("Audit Logs") == "audit-logs"

    @staticmethod
    def test_already_slug() -> None:
        """Verify an existing slug stays unchanged."""
        assert slugify("already-good") == "already-good"


class TestSqlalchemyToPydantic:
    """Verify sqlalchemy_to_pydantic conversion."""

    @staticmethod
    def test_creates_pydantic_model() -> None:
        """Verify conversion creates a pydantic model."""
        model = sqlalchemy_to_pydantic(User)
        assert issubclass(model, BaseModel)
        assert "UserSchema" in model.__name__

    @staticmethod
    def test_includes_all_columns_by_default() -> None:
        """Verify all columns are included by default."""
        model = sqlalchemy_to_pydantic(User)
        fields = set(model.model_fields.keys())
        assert "id" in fields
        assert "username" in fields
        assert "email" in fields
        assert "is_active" in fields
        assert "created_at" in fields

    @staticmethod
    def test_include_columns() -> None:
        """Verify include_columns restricts fields."""
        model = sqlalchemy_to_pydantic(User, include_columns=["id", "username"])
        fields = set(model.model_fields.keys())
        assert fields == {"id", "username"}

    @staticmethod
    def test_exclude_columns() -> None:
        """Verify exclude_columns removes fields."""
        model = sqlalchemy_to_pydantic(User, exclude_columns=["created_at"])
        fields = set(model.model_fields.keys())
        assert "created_at" not in fields

    @staticmethod
    def test_for_form_excludes_pk() -> None:
        """Verify for_form excludes the primary key."""
        model = sqlalchemy_to_pydantic(User, for_form=True)
        fields = set(model.model_fields.keys())
        assert "id" not in fields

    @staticmethod
    def test_from_attributes_config() -> None:
        """Verify from_attributes is enabled."""
        model = sqlalchemy_to_pydantic(User)
        assert model.model_config.get("from_attributes") is True

    @staticmethod
    def test_nullable_column_defaults_to_none() -> None:
        """Verify nullable columns without defaults allow None."""
        model = sqlalchemy_to_pydantic(NullableWidget)
        assert model.model_fields["label"].is_required() is False


class TestExtractSaDefault:
    """Verify _extract_sa_default extraction."""

    @staticmethod
    def test_column_without_default() -> None:
        """Verify a column without default returns None."""
        col = Column("test", Integer)
        assert _extract_sa_default(col) is None

    @staticmethod
    def test_column_with_scalar_default() -> None:
        """Verify a scalar default is extracted."""
        col = Column("status", String(20), default="pending")
        assert _extract_sa_default(col) == "pending"

    @staticmethod
    def test_column_with_callable_default_returns_none() -> None:
        """Verify a callable default returns None."""
        col = Column("created", DateTime, default=datetime.now)
        assert _extract_sa_default(col) is None

    @staticmethod
    def test_column_with_boolean_default() -> None:
        """Verify a boolean default is extracted."""
        col = Column("active", Boolean, default=True)
        assert _extract_sa_default(col) is True

    @staticmethod
    def test_column_with_sequence_default_returns_none() -> None:
        """Verify a non-ColumnDefault default returns None."""
        col = Column("seq", Integer, Sequence("seq_seq"))
        assert _extract_sa_default(col) is None
