# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastUI Admin is a Python package for building admin interfaces using FastUI, FastAPI, and SQLAlchemy. It's in early development (v0.1.0, Planning stage) and depends on FastUI's maturity.

Related learning resource: [fastui-tutorials](https://github.com/hasansezertasan/fastui-tutorials)

## Commands

All commands use Hatch. Run from the project root:

```bash
# Development
hatch run run                    # Start uvicorn dev server (port 5000)

# Testing
hatch run test                   # Run pytest
hatch run test-cov               # Run tests with coverage
hatch run cov                    # Full coverage pipeline

# Linting & Formatting
hatch run pre                    # Run all pre-commit hooks
hatch run lint:style             # Run ruff linter
hatch run lint:fmt               # Format with ruff
hatch run lint:typing            # Type check with mypy
hatch run lint:all               # Run style + typing

# Run single test
hatch run test tests/test_file.py::test_name
```

## Architecture

```
src/fastui_admin/
├── __init__.py  # Public API exports (BaseAdmin, BaseModelView, BaseView, etc.)
├── base.py      # BaseAdmin - main admin class, routing, session management, Starlette sub-app
├── views.py     # BaseView, AdminIndexView, BaseModelView - view hierarchy with CRUD endpoints
├── layout.py    # MasterLayout - navbar, footer, page rendering with FastUI components
├── utils.py     # SQLAlchemy → Pydantic model conversion, column inspection helpers
examples/
└── basic/
    └── main.py  # Working example app with User/Post models and seed data
```

**Core Flow:**
1. `BaseAdmin` is instantiated with engine/session_maker and configuration
2. Views are registered via `add_view()` (instantiated with admin reference)
3. `mount()` builds routes and creates a Starlette sub-app mounted on the FastAPI app
4. Each `BaseModelView` generates HTML endpoints (serve React frontend) and API endpoints (return FastUI JSON components)
5. CRUD operations: list (table + pagination), detail, create (form), edit (form with initial values), delete

**Key Dependencies:**
- `fastui` - UI components, prebuilt HTML, component serialization
- `fastapi` / `starlette` - Application and routing
- `sqlalchemy` - ORM, async session management
- `pydantic` - Dynamic model generation from SQLAlchemy models

## Code Style

- Python 3.8+ compatibility required
- Line length: 120 characters
- Uses Ruff for linting/formatting
- Relative imports banned (`ban-relative-imports = "all"`)
- First-party import: `fastui_admin`
- Type hints expected throughout
