# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Utility functions for FastUI Admin."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, NamedTuple, Protocol, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
)
from sqlalchemy.inspection import inspect
from sqlalchemy.schema import ColumnDefault

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from fastui import components as c
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.types import TypeEngine

__all__ = [
    "AdminProtocol",
    "FieldDefinition",
    "LayoutProtocol",
    "ViewProtocol",
    "get_python_type",
    "slugify",
    "sqlalchemy_to_pydantic",
]


logger = logging.getLogger(__name__)

# Type variable for SQLAlchemy generics (column/type holders), so signatures
# stay precise without writing an explicit `Any` the type gates forbid.
_T = TypeVar("_T")


class ViewProtocol(Protocol):
    """Structural interface for admin views.

    Lets ``views`` and ``layout`` reference registered views without importing
    ``fastui_admin.base`` (which would close an import cycle: base already
    imports both modules). ``BaseView`` satisfies this structurally.

    ``name``/``is_visible`` are ``ClassVar`` (not read-only properties) because
    views declare them as class variables, and checkers do not accept a
    ``ClassVar`` as the implementation of a read-only property member.
    """

    name: ClassVar[str]
    is_visible: ClassVar[bool]

    def get_url(self) -> str:
        """URL path for the view."""
        raise NotImplementedError  # pragma: no cover - protocol member


class LayoutProtocol(Protocol):
    """Structural interface for the page layout.

    Lets views render pages without importing ``fastui_admin.layout``
    (or ``base``). ``MasterLayout`` satisfies this structurally.
    """

    def render(self, *components: c.AnyComponent) -> list[c.AnyComponent]:
        """Render a full page from components."""
        raise NotImplementedError  # pragma: no cover - protocol member

    def get_prebuilt_html(
        self,
        *,
        title: str | None = None,
        api_root_url: str | None = None,
        api_path_mode: Literal["append", "query"] | None = None,
        api_path_strip: str | None = None,
    ) -> str:
        """Render the SPA shell HTML."""
        raise NotImplementedError  # pragma: no cover - protocol member


class AdminProtocol(Protocol):
    """Structural interface for the admin application.

    Lets ``views`` and ``layout`` reference the admin without importing
    ``fastui_admin.base`` (which would close an import cycle: base already
    imports both modules). ``BaseAdmin`` satisfies this structurally.
    """

    @property
    def base_url(self) -> str:
        """Base URL path the admin is mounted on."""
        raise NotImplementedError  # pragma: no cover - protocol member

    @property
    def title(self) -> str:
        """Admin interface title."""
        raise NotImplementedError  # pragma: no cover - protocol member

    @property
    def views(self) -> Sequence[ViewProtocol]:
        """Registered views for navigation."""
        raise NotImplementedError  # pragma: no cover - protocol member

    @property
    def layout(self) -> LayoutProtocol:
        """Page layout renderer."""
        raise NotImplementedError  # pragma: no cover - protocol member

    @property
    def session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Async session maker for database access."""
        raise NotImplementedError  # pragma: no cover - protocol member

    def get_relative_url(self, url: str) -> str:
        """Strip the base URL prefix from a path."""
        raise NotImplementedError  # pragma: no cover - protocol member


# create_model field definitions pair a (possibly optional) type with its
# FieldInfo. A NamedTuple (rather than a tuple alias) because the ruff RUF031
# style required here parenthesizes multi-element subscripts
# (``tuple[(A, B)]``), which some type checkers cannot parse.
class FieldDefinition(NamedTuple):
    """A ``create_model`` field definition: (type, FieldInfo) pair."""

    annotation: object
    field_info: object


# SQLAlchemy type to Python type mapping. Unannotated so lookups use plain
# MRO membership: annotating the map would force an explicit `Any` that the
# type gates forbid, and isinstance() rejects parameterized generics.
SA_TYPE_MAP = {
    BigInteger: int,
    SmallInteger: int,
    Integer: int,
    Float: float,
    Numeric: Decimal,
    String: str,
    Text: str,
    Boolean: bool,
    DateTime: datetime,
    Date: date,
    Time: time,
}


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug.

    Lowercases the name and replaces any non-alphanumeric characters with hyphens.

    Returns:
        URL-safe slug string.

    Examples:
        >>> from fastui_admin.utils import slugify
        >>> slugify("Audit Logs")
        'audit-logs'
        >>> slugify("My View!")
        'my-view'
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")


def get_python_type(sa_type: TypeEngine[_T]) -> type:
    """Get Python type from SQLAlchemy column type.

    Args:
        sa_type: SQLAlchemy column type to map.

    Returns:
        Mapped Python type, or str for unmapped types such as JSON or ARRAY.
    """
    for sa_cls, py_type in SA_TYPE_MAP.items():
        # Membership (not isinstance): isinstance() rejects parameterized
        # generics, so compare against the MRO directly. For concrete column
        # types this is equivalent to isinstance.
        if sa_cls in type(sa_type).__mro__:
            return py_type
    logger.warning(
        "No Python type mapping for SQLAlchemy type %s; defaulting to str.",
        type(sa_type).__name__,
    )
    return str


def _extract_sa_default(column: Column[_T]) -> object:
    """Extract a scalar default value from a SQLAlchemy column, if possible.

    Args:
        column: SQLAlchemy column to inspect.

    Returns:
        Scalar default value, or None when the default is callable,
        server-side, or absent.

    Note: ``server_default`` (e.g. ``text("CURRENT_TIMESTAMP")``) is intentionally
    ignored — it cannot be meaningfully represented as a Pydantic field default.
    """
    col_default = column.default
    if col_default is None:
        return None
    if not isinstance(col_default, ColumnDefault):
        return None
    # Cast (not annotate): assignment would narrow the declared type to Any.
    arg = cast("object", col_default.arg)
    # Only use scalar defaults; callables (like datetime.now) cannot be
    # serialized as Pydantic defaults.
    if callable(arg):
        return None
    return arg


def _should_include_column(
    col_name: str,
    include_columns: list[str] | None,
    exclude_columns: list[str],
    *,
    for_form: bool,
    pk_name: str | None,
) -> bool:
    """Decide whether a column belongs in the generated schema.

    Args:
        col_name: Column key to check.
        include_columns: Columns to include (None or empty means all).
        exclude_columns: Columns to exclude.
        for_form: Exclude the primary key when True.
        pk_name: Primary key column name, if any.

    Returns:
        True when the column should be included.
    """
    if include_columns and col_name not in include_columns:
        return False
    if col_name in exclude_columns:
        return False
    return not (for_form and col_name == pk_name)


def _build_field_info(column: Column[_T]) -> FieldDefinition:
    """Create a Pydantic field definition for a SQLAlchemy column.

    Args:
        column: SQLAlchemy column to convert.

    Returns:
        Tuple of field type and field info for ``create_model``.
    """
    py_type = get_python_type(column.type)
    col_name = column.key
    is_nullable = column.nullable
    default_value = _extract_sa_default(column)
    title = col_name.replace("_", " ").title()

    field_type: object = py_type | None if is_nullable else py_type

    if default_value is not None:
        return FieldDefinition(field_type, Field(default=default_value, title=title))
    if is_nullable:
        return FieldDefinition(field_type, Field(default=None, title=title))
    return FieldDefinition(field_type, Field(default=..., title=title))


def sqlalchemy_to_pydantic(
    model: type[DeclarativeBase],
    include_columns: list[str] | None = None,
    exclude_columns: list[str] | None = None,
    *,
    for_form: bool = False,
) -> type[BaseModel]:
    """
    Generate a Pydantic model from a SQLAlchemy model.

    Args:
        model: SQLAlchemy model class
        include_columns: Columns to include (None = all)
        exclude_columns: Columns to exclude
        for_form: If True, exclude primary key (for create/edit forms)

    Returns:
        Dynamically created Pydantic model
    """
    mapper = inspect(model)
    exclude_columns = exclude_columns or []

    # Get primary key column name
    pk_name = cast(
        "str | None", mapper.primary_key[0].name if mapper.primary_key else None
    )

    fields: dict[str, FieldDefinition] = {}

    for column in mapper.columns:
        if not _should_include_column(
            column.key,
            include_columns,
            exclude_columns,
            for_form=for_form,
            pk_name=pk_name,
        ):
            continue
        fields[column.key] = _build_field_info(column)

    # Create a base class with the config
    class BaseSchema(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    # Create the model with from_attributes config. The ignores are for the
    # create_model overloads, which cannot match a **dict of field definitions:
    # each entry may target any parameter, so the value type would have to be
    # compatible with every named parameter at once. The cast still constrains
    # the result. (mypy and zuban share the call-overload suppression below;
    # basedpyright, ty, and pyrefly need their own comments and read no
    # others'.)
    return cast(
        "type[BaseModel]",
        create_model(  # pyrefly: ignore[no-matching-overload]
            f"{model.__name__}Schema",
            __base__=BaseSchema,
            **fields,  # pyright: ignore[reportCallIssue, reportArgumentType]
        ),  # type: ignore[call-overload]  # ty: ignore[no-matching-overload]
    )
