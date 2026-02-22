# FastUI Admin

[![CI](https://github.com/hasansezertasan/FastUI-Admin/actions/workflows/ci.yml/badge.svg)](https://github.com/hasansezertasan/FastUI-Admin/actions?query=event%3Apush+branch%3Amain+workflow%3ACI)
[![pypi](https://img.shields.io/pypi/v/fastui-admin.svg)](https://pypi.python.org/pypi/fastui-admin)
[![versions](https://img.shields.io/pypi/pyversions/fastui-admin.svg)](https://github.com/hasansezertasan/FastUI-Admin)
[![license](https://img.shields.io/github/license/hasansezertasan/FastUI-Admin.svg)](https://github.com/hasansezertasan/FastUI-Admin/blob/main/LICENSE)

Build admin interfaces for [FastAPI](https://fastapi.tiangolo.com/) applications using [FastUI](https://github.com/pydantic/FastUI) and [SQLAlchemy](https://www.sqlalchemy.org/).

Inspired by [Flask-Admin](https://github.com/flask-admin/flask-admin) and [SQLAdmin](https://github.com/aminalaee/sqladmin).

> **Note:** FastUI Admin is an active work in progress. The API may change as the project matures alongside FastUI.

## Features

- Automatic CRUD interface for SQLAlchemy models
- List view with pagination
- Detail, create, edit, and delete views
- Auto-generated forms from model columns
- Navigation bar with registered model views
- Configurable columns, page size, and permissions
- Mounts as a sub-application on FastAPI or Starlette

## Installation

```console
pip install fastui-admin
```

For async SQLite support (used in examples):

```console
pip install aiosqlite greenlet
```

## Quick Start

```python
from fastapi import FastAPI
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastui_admin import BaseAdmin, BaseModelView


# Define your models
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# Define admin views
class UserAdmin(BaseModelView, model=User):
    name = "Users"
    column_list = ["id", "username", "email", "is_active"]
    page_size = 25


# Set up the app
app = FastAPI()
engine = create_async_engine("sqlite+aiosqlite:///./db.sqlite3")

admin = BaseAdmin(app, engine, title="My Admin")
admin.add_view(UserAdmin)
admin.mount()
```

Run the app and visit `http://localhost:8000/admin/`.

## Configuration

### BaseAdmin

| Parameter       | Type                                 | Default    | Description                   |
| --------------- | ------------------------------------ | ---------- | ----------------------------- |
| `app`           | `FastAPI \| Starlette`               | required   | Application to mount admin on |
| `engine`        | `Engine \| AsyncEngine`              | `None`     | SQLAlchemy engine             |
| `session_maker` | `sessionmaker \| async_sessionmaker` | `None`     | Custom session maker          |
| `title`         | `str`                                | `"Admin"`  | Admin interface title         |
| `base_url`      | `str`                                | `"/admin"` | Base URL path                 |
| `logo_url`      | `str`                                | `None`     | Logo image URL                |

### BaseModelView

| Parameter             | Type          | Default     | Description                  |
| --------------------- | ------------- | ----------- | ---------------------------- |
| `model`               | class keyword | required    | SQLAlchemy model class       |
| `name`                | `str`         | Model name  | Display name                 |
| `column_list`         | `list[str]`   | All columns | Columns to show in list view |
| `column_exclude_list` | `list[str]`   | `[]`        | Columns to exclude from list |
| `page_size`           | `int`         | `25`        | Items per page               |
| `can_create`          | `bool`        | `True`      | Enable create action         |
| `can_edit`            | `bool`        | `True`      | Enable edit action           |
| `can_delete`          | `bool`        | `True`      | Enable delete action         |
| `can_view_details`    | `bool`        | `True`      | Enable detail view           |

## Examples

See the [examples/basic](examples/basic/) directory for a complete working example with User and Post models.

```bash
# Run the example
uvicorn examples.basic.main:app --port 5000

# Seed sample data
curl -X POST http://localhost:5000/seed

# Visit admin interface
open http://localhost:5000/admin/
```

## Feature Parity

Comparison with [Flask-Admin](https://github.com/flask-admin/flask-admin) and [SQLAdmin](https://github.com/aminalaee/sqladmin) (ref: [sqladmin#316](https://github.com/aminalaee/sqladmin/issues/316)).

### General Features

| Feature                 | Flask-Admin | SQLAdmin | FastUI Admin |
| ----------------------- | ----------- | -------- | ------------ |
| ModelView               | ✅          | ✅       | ✅           |
| BaseView (custom pages) | ✅          | ❌       | ✅           |
| Authentication          | ✅          | ✅       | ❌           |
| Ajax / search           | ✅          | ❌       | ❌           |
| Custom templates        | ✅          | ✅       | ❌           |
| Batch actions           | ✅          | ❌       | ❌           |
| Inline models           | ✅          | ❌       | ❌           |
| Export (CSV, etc.)      | ✅          | ✅       | ❌           |
| File/image upload       | ✅          | ✅       | ❌           |
| I18n                    | ✅          | ❌       | ❌           |
| Async support           | ❌          | ✅       | ✅           |

### ModelView Options

| Option                   | Flask-Admin | SQLAdmin | FastUI Admin |
| ------------------------ | ----------- | -------- | ------------ |
| `can_create`             | ✅          | ✅       | ✅           |
| `can_edit`               | ✅          | ✅       | ✅           |
| `can_delete`             | ✅          | ✅       | ✅           |
| `can_view_details`       | ✅          | ✅       | ✅           |
| `can_export`             | ✅          | ✅       | ❌           |
| `column_list`            | ✅          | ✅       | ✅           |
| `column_exclude_list`    | ✅          | ✅       | ✅           |
| `column_formatters`      | ✅          | ✅       | ❌           |
| `column_searchable_list` | ✅          | ✅       | ❌           |
| `column_sortable_list`   | ✅          | ✅       | ❌           |
| `column_default_sort`    | ✅          | ✅       | ❌           |
| `column_labels`          | ✅          | ✅       | ❌           |
| `page_size`              | ✅          | ✅       | ✅           |
| `form_include_pk`        | ✅          | ✅       | ❌           |
| `form_columns`           | ✅          | ✅       | ❌           |
| `form_excluded_columns`  | ✅          | ✅       | ❌           |
| `form_widget_args`       | ✅          | ✅       | ❌           |
| `form_args`              | ✅          | ✅       | ❌           |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full feature roadmap, including planned support for column sorting, search/filtering, authentication, export, and more.

## Related

- [FastUI](https://github.com/pydantic/FastUI) - Build web UIs with declarative Python
- [FastUI Tutorials](https://github.com/hasansezertasan/fastui-tutorials) - Learning resource for FastUI
- [SQLAdmin](https://github.com/aminalaee/sqladmin) - Admin interface for SQLAlchemy (Jinja2-based)
- [Flask-Admin](https://github.com/flask-admin/flask-admin) - Admin interface for Flask

## Credits

Vibe coded by [Claude Opus 4.5](https://claude.ai), reviewed and tested by [@hasansezertasan](https://github.com/hasansezertasan).

## License

`fastui-admin` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
