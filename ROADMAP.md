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

All this is intermixed with bug fixes, reviews, and community feedback.
