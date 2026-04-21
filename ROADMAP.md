# Roadmap

This is a tentative roadmap for FastUI Admin. It will be updated as things evolve. Some items might be discarded, others might be added later.

Inspired by the roadmap format used by [FastAPI](https://github.com/tiangolo/fastapi/issues/10370), [SQLModel](https://github.com/tiangolo/sqlmodel/issues/654), and [Typer](https://github.com/tiangolo/typer/issues/678).

## Current Status

FastUI Admin is in early development (v0.1.0). The core CRUD functionality works with async SQLAlchemy models. See the [Feature Parity table](README.md#feature-parity) for a comparison with Flask-Admin and SQLAdmin.

## Roadmap

### ModelView Enhancements

- [ ] Column sorting (`column_sortable_list`, `column_default_sort`)
- [ ] Column search and filtering (`column_searchable_list`)
- [ ] Column labels (`column_labels`)
- [ ] Column formatters (`column_formatters`)
- [ ] Form column configuration (`form_columns`, `form_excluded_columns`)
- [ ] Form widget customization (`form_widget_args`, `form_args`)
- [ ] Form include primary key option (`form_include_pk`)
- [ ] Export to CSV (`can_export`)

### Core Features

- [ ] Authentication support (`AuthenticationBackend`)
- [ ] Relationship handling (display related models, foreign key dropdowns)
- [ ] Batch actions (select multiple rows, bulk delete)
- [ ] Custom actions on model views

### UI & UX

- [ ] Custom templates / component overrides
- [ ] File and image upload fields
- [ ] Confirmation dialog for delete actions
- [ ] Flash messages / toast notifications for success/error
- [ ] Dark mode support

### Infrastructure

- [ ] Sync engine support (currently async-only)
- [ ] Internationalization (i18n)
- [ ] Reference (API) documentation
- [ ] More examples (multi-model relationships, custom views, authentication)

## Known Limitations

These are accepted design trade-offs in the current implementation, not bugs. They may be addressed in future versions.

- **`BaseModelView` uses raw `__tablename__` for URLs, `BaseView` uses `slugify(name)`**: SQLAlchemy table names are valid identifiers by convention, so this works in practice. Unifying the approach would require a migration path for existing routes.
- **No guard against duplicate route names**: If two model views reference the same `__tablename__`, Starlette will raise on duplicate route names. This requires user error (two models sharing a table name) and is unlikely in practice.
- **Mixed relative/absolute URL patterns in `GoToEvent`**: Some navigation uses relative URLs (`./edit`, `./create`) and others use absolute paths (`{self.get_url()}/`). Both work correctly with FastUI's SPA routing. Standardizing could break navigation edge cases without clear benefit.

All this is intermixed with bug fixes, reviews, and community feedback.
