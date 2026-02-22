# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Utility functions for FastUI Admin."""

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeEngine

# SQLAlchemy type to Python type mapping
SA_TYPE_MAP: Dict[Type[TypeEngine[Any]], type] = {
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

    Examples:
        >>> slugify("Audit Logs")
        'audit-logs'
        >>> slugify("My View!")
        'my-view'
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")


def get_python_type(sa_type: TypeEngine[Any]) -> type:
    """Get Python type from SQLAlchemy column type."""
    for sa_cls, py_type in SA_TYPE_MAP.items():
        if isinstance(sa_type, sa_cls):
            return py_type
    # Default to str for unknown types
    return str


def _extract_sa_default(column: Any) -> Any:
    """Extract a scalar default value from a SQLAlchemy column, if possible.

    Returns the default value if it's a simple scalar (int, str, bool, etc.),
    or None if the default is a callable, server-side default, or absent.
    """
    col_default = column.default
    if col_default is None:
        return None
    arg = col_default.arg
    # Only use scalar defaults; callables (like datetime.now) can't be serialized as Pydantic defaults
    if callable(arg):
        return None
    return arg


def sqlalchemy_to_pydantic(
    model: Type[DeclarativeBase],
    include_columns: Optional[List[str]] = None,
    exclude_columns: Optional[List[str]] = None,
    for_form: bool = False,
) -> Type[BaseModel]:
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
    pk_name = mapper.primary_key[0].name if mapper.primary_key else None

    fields: Dict[str, Any] = {}

    for column in mapper.columns:
        col_name = column.key

        # Filter columns
        if include_columns and col_name not in include_columns:
            continue
        if col_name in exclude_columns:
            continue
        if for_form and col_name == pk_name:
            continue  # Skip PK for forms

        # Determine Python type
        py_type = get_python_type(column.type)

        # Determine nullability and default value independently
        is_nullable = column.nullable
        default_value = _extract_sa_default(column)
        title = col_name.replace("_", " ").title()

        field_type: type = Optional[py_type] if is_nullable else py_type  # type: ignore[assignment]

        field_info: Tuple[Any, Any]
        if default_value is not None:
            field_info = (field_type, Field(default=default_value, title=title))
        elif is_nullable:
            field_info = (field_type, Field(default=None, title=title))
        else:
            field_info = (field_type, Field(default=..., title=title))
        fields[col_name] = field_info

    # Create a base class with the config
    class BaseSchema(BaseModel):
        model_config = ConfigDict(from_attributes=True)

    # Create the model with from_attributes config
    return create_model(
        f"{model.__name__}Schema",
        __base__=BaseSchema,
        **fields,
    )


def get_pk_column(model: Type[DeclarativeBase]) -> str:
    """Get the primary key column name for a SQLAlchemy model."""
    mapper = inspect(model)
    if mapper.primary_key:
        return str(mapper.primary_key[0].name)
    msg = f"Model {model.__name__} has no primary key"
    raise ValueError(msg)


def get_model_columns(model: Type[DeclarativeBase]) -> List[str]:
    """Get all column names for a SQLAlchemy model."""
    mapper = inspect(model)
    return [c.key for c in mapper.columns]
