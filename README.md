# fastui_admin

[![CI](https://github.com/hasansezertasan/fastui-admin/actions/workflows/ci.yml/badge.svg)](https://github.com/hasansezertasan/fastui-admin/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/codecov/c/github/hasansezertasan/fastui-admin)](https://codecov.io/gh/hasansezertasan/fastui-admin)
[![Documentation Status](https://img.shields.io/github/deployments/hasansezertasan/fastui-admin/github-pages?label=docs)](https://hasansezertasan.github.io/fastui-admin)
[![PyPI - Version](https://img.shields.io/pypi/v/fastui-admin.svg)](https://pypi.org/project/fastui-admin)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fastui-admin.svg)](https://pypi.org/project/fastui-admin)
[![License - MIT](https://img.shields.io/github/license/hasansezertasan/fastui-admin.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/hasansezertasan/fastui-admin?style=social)](https://github.com/hasansezertasan/fastui-admin/stargazers)
[![Latest Commit](https://img.shields.io/github/last-commit/hasansezertasan/fastui-admin)](https://github.com/hasansezertasan/fastui-admin)

[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/hasansezertasan/fastui-admin/badge)](https://scorecard.dev/viewer/?uri=github.com/hasansezertasan/fastui-admin)
[![GitHub Tag](https://img.shields.io/github/tag/hasansezertasan/fastui-admin?include_prereleases=&sort=semver&color=black)](https://github.com/hasansezertasan/fastui-admin/releases/)

[![Downloads](https://pepy.tech/badge/fastui-admin)](https://pepy.tech/project/fastui-admin)
[![Downloads/Month](https://pepy.tech/badge/fastui-admin/month)](https://pepy.tech/project/fastui-admin)
[![Downloads/Week](https://pepy.tech/badge/fastui-admin/week)](https://pepy.tech/project/fastui-admin)

> Build better Admin UIs faster.

Build admin interfaces for [FastAPI](https://fastapi.tiangolo.com/) applications using [FastUI](https://github.com/pydantic/FastUI) and [SQLAlchemy](https://www.sqlalchemy.org/).

Inspired by [Flask-Admin](https://github.com/flask-admin/flask-admin) and [SQLAdmin](https://github.com/aminalaee/sqladmin).

> **Note:** FastUI Admin is an active work in progress. The API may change as the project matures alongside FastUI.

-----

## Table of Contents

- [Installation](#installation)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Examples](#examples)
- [Feature Parity](#feature-parity)
- [Roadmap](#roadmap)
- [Related](#related)
- [Support](#support-heart)
- [Motivation](#motivation)
- [About](#about)
- [Author](#author-person_with_crown)
- [Analysis](#analysis)
- [Contributing](#contributing-heart)
- [Development](#development-toolbox)
- [Releasing](#releasing)
- [Credits](#credits)
- [License](#license-scroll)
- [Changelog](#changelog-memo)

## Installation

`fastui_admin` is a library. Add it to your project as a dependency:

```console
uv add fastui-admin
```

Or with `pip`:

```console
pip install fastui-admin
```

For async SQLite support (used in examples):

```console
pip install aiosqlite greenlet
```

### Verify the installation

The package root is importable after installation:

```pycon
>>> from fastui_admin import __doc__
>>> isinstance(__doc__, str)
True

```

<!--
pytest runs the pycon examples in this file (--doctest-glob=README.md).
doctest cannot see Markdown and ends an example's expected output at the first
blank line, so leave a blank line before every closing fence -- as the example
above does. Without it the closing delimiter is read as part of the expected
output and the example fails ("Expected: 2 / Got: 2"). Examples with no output
line at all need the blank line too.
-->

## Features

- Automatic CRUD interface for SQLAlchemy models
- List view with pagination
- Detail, create, edit, and delete views
- Auto-generated forms from model columns
- Navigation bar with registered model views
- Configurable columns, page size, and permissions
- Mounts as a sub-application on FastAPI or Starlette

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

See the [examples/simple](examples/simple/) directory for a complete working example with User and Post models.

```bash
# Run the example
uvicorn examples.simple.main:app --port 5000

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

See the [Roadmap issue](https://github.com/hasansezertasan/fastui-admin/issues/5) for the full feature roadmap, including planned support for column sorting, search/filtering, authentication, export, and more.

## Related

- [FastUI](https://github.com/pydantic/FastUI) - Build web UIs with declarative Python
- [FastUI Tutorials](https://github.com/hasansezertasan/fastui-tutorials) - Learning resource for FastUI
- [SQLAdmin](https://github.com/aminalaee/sqladmin) - Admin interface for SQLAlchemy (Jinja2-based)
- [Flask-Admin](https://github.com/flask-admin/flask-admin) - Admin interface for Flask

## Support :heart:

If you have any questions or need help, feel free to open an issue on the [GitHub repository][fastui_admin].

## Motivation

Existing SQLAlchemy admin interfaces render server-side HTML. FastUI Admin brings the same ModelView ergonomics — list, detail, create, edit, and delete views with configurable columns and page size — to [FastUI](https://github.com/pydantic/FastUI)-based [FastAPI](https://fastapi.tiangolo.com/) applications, mounting as a sub-application on FastAPI or Starlette.

## About

FastUI Admin provides an automatic CRUD interface for SQLAlchemy models (sync and async), with auto-generated forms from model columns, a navigation bar with registered model views, and configurable columns, page size, and permissions.

## Author :person_with_crown:

This project is maintained by [Hasan Sezer Taşan][author], It's me :wave:

## Analysis

- [Snyk Python Package Health Analysis](https://snyk.io/advisor/python/fastui-admin)
- [Libraries.io - PyPI](https://libraries.io/pypi/fastui-admin)
- [Safety DB](https://data.safetycli.com/packages/pypi/fastui-admin)
- [PePy Download Stats](https://www.pepy.tech/projects/fastui-admin)
- [PyPI Download Stats](https://pypistats.org/packages/fastui-admin)
- [Pip Trends Download Stats](https://piptrends.com/package/fastui-admin)
- [PyPI Map Dependency Graph](https://pypimap.com/package/fastui-admin)

## Contributing :heart:

Any contributions are welcome! Please follow the [Contributing Guidelines](./.github/CONTRIBUTING.md) to contribute to this project.

## Development :toolbox:

See the [Contributing Guidelines](./.github/CONTRIBUTING.md#your-first-code-contribution)
for local setup, the common development tasks (exposed via [mise](https://mise.jdx.dev)),
building and previewing the documentation, and the VS Code debugging configurations.

## Releasing

Versioning and releases are automated with [release-please](https://github.com/googleapis/release-please), driven by [Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/) PR titles squash-merged into `main`. release-please maintains a release PR that bumps the version and `CHANGELOG.md`; merging it tags the release and publishes to PyPI. See the [Contributing Guidelines](./.github/CONTRIBUTING.md#releasing) for the commit conventions, and the [Repository setup](./REPOSITORY_SETUP.rst) guide for one-time configuration and optional post-launch integrations such as a social preview, downstream packaging, and Repology.

Pause merges that change `.github/workflows/`, including Renovate action-pin updates, from merging a release PR until the entire Release run finishes. Workflow differences between the release commit and current `main` can block tag or release creation with a 403 when using `GITHUB_TOKEN`. See [Release recovery](./REPOSITORY_SETUP.rst#keep-workflow-changes-out-of-an-active-release) for prevention and recovery steps.

For adopting this project's tooling into an existing package, or reconciling a
template update with existing project behavior, see the **Template updates** and
**Adopting into an existing project** sections of
[REPOSITORY_SETUP.rst](./REPOSITORY_SETUP.rst). They cover the baseline,
workflow and required-check overlap, custom tooling and documentation, and ask
for a decision before consequential cleanup. Work through the repository
settings and release steps in the same file.

## Credits

<<<<<<< before updating
Vibe coded by [Claude Opus 4.5](https://claude.ai), reviewed and tested by [@hasansezertasan](https://github.com/hasansezertasan).

This package was created with [Copier](https://github.com/copier-org/copier) and the [hasansezertasan/copier-pyproject](https://github.com/hasansezertasan/copier-pyproject) project template.
=======
Generated from [copier-pyproject](https://github.com/hasansezertasan/copier-pyproject).
>>>>>>> after updating

## License :scroll:

`fastui-admin` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Changelog :memo:

For a detailed list of changes, please refer to the [CHANGELOG](./CHANGELOG.md).

<!-- Refs -->
[author]: https://github.com/hasansezertasan
[fastui_admin]: https://github.com/hasansezertasan/fastui-admin
