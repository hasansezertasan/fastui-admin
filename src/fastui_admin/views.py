# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""View classes for FastUI Admin."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, cast

from fastui import components as c
from fastui.components.display import DisplayLookup
from fastui.events import BackEvent, GoToEvent
from pydantic import BaseModel, ValidationError, create_model
from sqlalchemy import func as sa_func, select as sa_select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect as sa_inspect
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from typing_extensions import override

from fastui_admin.utils import slugify, sqlalchemy_to_pydantic

logger = logging.getLogger(__name__)

# Empty Pydantic model required by FastUI's ModelForm for the delete confirmation
# button (no actual form fields needed).
_DeleteConfirmModel = create_model("DeleteConfirm")

# Error-message templates (module level so each fits on one 88-col line).
_LIST_ERROR = "Failed to load {name} list. Check database connection and server logs."
_LOAD_ERROR = "Failed to load {name}. Check database connection and server logs."

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.orm import DeclarativeBase
    from starlette.requests import Request

    from fastui_admin.utils import AdminProtocol

__all__ = ["AdminIndexView", "BaseModelView", "BaseView"]


class BaseView:
    """Base class for all admin views.

    Provides common functionality for visibility, URL generation, and rendering.
    """

    name: ClassVar[str] = ""
    category: ClassVar[str | None] = None
    icon: ClassVar[str | None] = None
    is_visible: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Set default name from class name if not explicitly provided."""
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("name"):
            cls.name = cls.__name__

    def __init__(self, admin: AdminProtocol) -> None:
        """Initialize view with admin reference.

        Args:
            admin: The BaseAdmin instance this view belongs to.
        """
        self._admin: AdminProtocol = admin

    @property
    def admin(self) -> AdminProtocol:
        """Admin instance."""
        return self._admin

    def get_url(self) -> str:
        """Get the URL for this view.

        Returns:
            URL for this view.
        """
        return f"{self._admin.base_url}/{slugify(self.name)}"

    async def render(  # noqa: PLR6301
        self, _request: Request
    ) -> list[c.AnyComponent]:
        """Render view components. Override in subclasses.

        Returns:
            List of FastUI components.
        """
        return []


class AdminIndexView(BaseView):
    """Default index/dashboard view for the admin interface."""

    name: ClassVar[str] = "Dashboard"
    icon: ClassVar[str | None] = "home"

    @override
    def get_url(self) -> str:
        """Index view is at root.

        Returns:
            Base URL of the admin interface.
        """
        return self._admin.base_url

    @override
    async def render(self, _request: Request) -> list[c.AnyComponent]:
        """Render dashboard with welcome message and links to model views.

        Returns:
            List of FastUI components.
        """
        model_links: list[c.AnyComponent] = []
        for view in self._admin.views:
            if view.is_visible and view != self and isinstance(view, BaseModelView):
                url = self._admin.get_relative_url(view.get_url())

                model_links.append(
                    c.Link(
                        components=[c.Text(text=view.name)],
                        on_click=GoToEvent(url=url),
                        class_name="btn btn-outline-primary me-2 mb-2",
                    )
                )

        page_components: list[c.AnyComponent] = [
            c.Heading(text=f"Welcome to {self._admin.title}", level=2),
            c.Paragraph(text="Select a model from the navigation to manage your data."),
        ]

        if model_links:
            page_components.append(c.Div(components=model_links, class_name="mt-3"))

        return self._admin.layout.render(*page_components)


class BaseModelView(BaseView):
    """View for SQLAlchemy model CRUD operations.

    Only integer primary keys are currently supported.

    Usage:
        ```python
        class UserAdmin(BaseModelView, model=User):
            name = "Users"
            column_list = ["id", "username", "email"]
            page_size = 25
        ```
    """

    # Model configuration (set via __init_subclass__)
    model: ClassVar[type[DeclarativeBase]]

    # List view configuration
    column_list: ClassVar[list[str] | None] = None  # None = all columns
    column_exclude_list: ClassVar[list[str]] = []
    page_size: ClassVar[int] = 25

    # Permissions
    can_create: ClassVar[bool] = True
    can_edit: ClassVar[bool] = True
    can_delete: ClassVar[bool] = True
    can_view_details: ClassVar[bool] = True

    def __init_subclass__(
        cls, model: type[DeclarativeBase] | None = None, **kwargs: object
    ) -> None:
        """Capture model from class definition syntax.

        Allows: class UserAdmin(BaseModelView, model=User)
        Also sets a default name from the model's table name if not
        explicitly provided.

        Raises:
            TypeError: If a concrete subclass omits the model parameter.
            ValueError: If page_size is not positive.
        """
        if model is not None:
            cls.model = model
            if "name" not in cls.__dict__:
                raw_name = str(getattr(model, "__tablename__", model.__name__))
                # `name` is declared on BaseView; this only fills the default.
                # setattr (not assignment) so checkers do not demand a new
                # attribute annotation for an inherited ClassVar.
                setattr(cls, "name", raw_name.replace("_", " ").title())  # noqa: B010
        elif not hasattr(cls, "model"):
            msg = (
                f"{cls.__name__} must specify model=MyModel. "
                "Example: class MyAdmin(BaseModelView, model=MyModel)"
            )
            raise TypeError(msg)
        # Last: BaseView fills the class name only when nothing above set one.
        # (Calling it first would make the table-title branch unreachable.)
        super().__init_subclass__(**kwargs)

        if "page_size" in cls.__dict__ and cls.__dict__["page_size"] <= 0:
            msg = f"page_size must be positive, got {cls.__dict__['page_size']}"
            raise ValueError(msg)

    def __init__(self, admin: AdminProtocol) -> None:
        """Initialize model view."""
        super().__init__(admin)

        self._pk_name: str = self._get_pk_name()
        self._columns: list[str] | None = None
        self._pydantic_model: type[BaseModel] | None = None
        self._form_model: type[BaseModel] | None = None

    def _get_pk_name(self) -> str:
        """Get primary key column name.

        Returns:
            Name of the primary key column.

        Raises:
            ValueError: If the model has no primary key.
        """
        mapper = sa_inspect(self.model)
        if mapper.primary_key:
            # Cast (not annotate): assignment would narrow the type to Any.
            return str(cast("str", mapper.primary_key[0].name))
        msg = f"Model {self.model.__name__} has no primary key"
        raise ValueError(msg)

    def _get_columns(self) -> list[str]:
        """Get list of column names for list view.

        Cached after first call.

        Returns:
            List of column names for the list view.
        """
        if self._columns is not None:
            return self._columns

        mapper = sa_inspect(self.model)
        all_columns = [col.key for col in mapper.columns]

        if self.column_list:
            invalid = [col for col in self.column_list if col not in all_columns]
            if invalid:
                logger.warning(
                    "column_list for %s contains invalid columns: %s. Available: %s",
                    self.name,
                    invalid,
                    all_columns,
                )
            self._columns = [col for col in self.column_list if col in all_columns]
        else:
            self._columns = [
                col for col in all_columns if col not in self.column_exclude_list
            ]

        return self._columns

    def _get_pydantic_model(self) -> type[BaseModel]:
        """Get or create Pydantic model for this SQLAlchemy model.

        Returns:
            Pydantic model for this SQLAlchemy model.
        """
        if self._pydantic_model is None:
            self._pydantic_model = sqlalchemy_to_pydantic(
                self.model, include_columns=self._get_columns()
            )
        return self._pydantic_model

    def _get_form_model(self) -> type[BaseModel]:
        """Get Pydantic model for forms (excludes PK).

        Returns:
            Pydantic model for forms.
        """
        if self._form_model is None:
            self._form_model = sqlalchemy_to_pydantic(
                self.model, include_columns=self._get_columns(), for_form=True
            )
        return self._form_model

    @property
    def _table_name(self) -> str:
        """URL-safe table name for routing."""
        return str(getattr(self.model, "__tablename__", self.model.__name__.lower()))

    @override
    def get_url(self) -> str:
        """Get base URL for this model view.

        Returns:
            Base URL for this model view.
        """
        return f"{self._admin.base_url}/{self._table_name}"

    def get_routes(self) -> list[Route]:
        """Get all routes for this model view.

        Returns:
            List of routes for this model view.
        """
        table_name = self._table_name
        base = f"/{table_name}"

        routes = [
            Route(f"{base}/", endpoint=self._list_html, name=f"{table_name}_list"),
            Route(
                f"/api{base}/", endpoint=self._list_api, name=f"{table_name}_list_api"
            ),
        ]

        if self.can_create:
            routes.extend([
                Route(
                    f"{base}/create",
                    endpoint=self._create_html,
                    name=f"{table_name}_create",
                ),
                Route(
                    f"/api{base}/create",
                    endpoint=self._create_api,
                    methods=["GET", "POST"],
                    name=f"{table_name}_create_api",
                ),
            ])

        if self.can_view_details:
            routes.extend([
                Route(
                    f"{base}/{{pk:int}}",
                    endpoint=self._detail_html,
                    name=f"{table_name}_detail",
                ),
                Route(
                    f"/api{base}/{{pk:int}}",
                    endpoint=self._detail_api,
                    name=f"{table_name}_detail_api",
                ),
            ])

        if self.can_edit:
            routes.extend([
                Route(
                    f"{base}/{{pk:int}}/edit",
                    endpoint=self._edit_html,
                    name=f"{table_name}_edit",
                ),
                Route(
                    f"/api{base}/{{pk:int}}/edit",
                    endpoint=self._edit_api,
                    methods=["GET", "POST"],
                    name=f"{table_name}_edit_api",
                ),
            ])

        if self.can_delete:
            routes.append(
                Route(
                    f"/api{base}/{{pk:int}}/delete",
                    endpoint=self._delete_api,
                    methods=["POST"],
                    name=f"{table_name}_delete_api",
                )
            )

        return routes

    def _error_response(
        self, message: str, *, back_url: str | None = None, status_code: int = 400
    ) -> JSONResponse:
        """Return a JSON response rendering an error page in the admin UI.

        Args:
            message: Error message to display.
            back_url: URL for the back button. Defaults to model list.
            status_code: HTTP status code (default: 400).

        Returns:
            JSON response rendering an error page.
        """
        if back_url is None:
            back_url = f"{self.get_url()}/"
        components = self._admin.layout.render(
            c.Heading(text="Error", level=2),
            c.Paragraph(text=message),
            c.Link(
                components=[c.Text(text="← Go Back")],
                on_click=GoToEvent(url=back_url),
                class_name="btn btn-secondary",
            ),
        )
        return JSONResponse(
            [comp.model_dump(mode="json", exclude_none=True) for comp in components],
            status_code=status_code,
        )

    # --- HTML Endpoints (serve the SPA shell that loads the React frontend) ---

    async def _list_html(self, _request: Request) -> HTMLResponse:
        """Serve frontend HTML for list view.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"{self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _detail_html(self, _request: Request) -> HTMLResponse:
        """Serve frontend HTML for detail view.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"{self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _create_html(self, _request: Request) -> HTMLResponse:
        """Serve frontend HTML for create view.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"Create {self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _edit_html(self, _request: Request) -> HTMLResponse:
        """Serve frontend HTML for edit view.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"Edit {self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    # --- API Endpoints (return FastUI components as JSON) ---

    def _get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Get session maker from admin.

        Always available — BaseAdmin.__init__ requires engine or session_maker.

        Returns:
            Async session maker from the admin instance.
        """
        return self._admin.session_maker

    async def _fetch_list_page(
        self, page: int, page_size: int
    ) -> tuple[int, list[BaseModel], type[BaseModel]]:
        """Fetch one page of rows with the total count.

        Returns:
            Tuple of total count, validated rows, and Pydantic model.
        """
        async with self._get_session_maker()() as session:
            # pylint: disable-next=not-callable  # sa.func attrs resolve dynamically
            count_stmt = sa_select(sa_func.count()).select_from(self.model)
            total = (await session.execute(count_stmt)).scalar() or 0

            pk_column = sa_inspect(self.model).columns[self._pk_name]
            stmt = (
                sa_select(self.model)
                .order_by(pk_column)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            items = result.scalars().all()

            # Convert inside session to avoid detached instance access
            pydantic_model = self._get_pydantic_model()
            data = [
                pydantic_model.model_validate(item, from_attributes=True)
                for item in items
            ]
            return total, data, pydantic_model

    def _build_list_columns(self) -> list[DisplayLookup]:
        """Build table columns for the list view.

        Returns:
            List of display lookups for table columns.
        """
        columns: list[DisplayLookup] = []
        for col_name in self._get_columns():
            col = DisplayLookup(field=col_name)
            if col_name == self._pk_name and self.can_view_details:
                col = DisplayLookup(
                    field=col_name, on_click=GoToEvent(url=f"./{{{self._pk_name}}}")
                )
            columns.append(col)
        return columns

    async def _list_api(self, request: Request) -> JSONResponse:
        """Return list view components.

        Returns:
            JSON response with FastUI components.
        """
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        page_size = self.page_size

        try:
            total, data, pydantic_model = await self._fetch_list_page(page, page_size)
        except SQLAlchemyError:
            logger.exception("Error listing %s", self.name)
            return self._error_response(
                _LIST_ERROR.format(name=self.name), status_code=500
            )

        columns = self._build_list_columns()

        header_components: list[c.AnyComponent] = [c.Heading(text=self.name, level=2)]

        if self.can_create:
            header_components.append(
                c.Link(
                    components=[c.Text(text=f"+ Create New {self.name}")],
                    on_click=GoToEvent(url="./create"),
                    class_name="btn btn-primary mb-3",
                )
            )

        table_component = c.Table(data=data, data_model=pydantic_model, columns=columns)

        pagination_component = c.Pagination(page=page, page_size=page_size, total=total)

        components = self._admin.layout.render(
            c.Div(components=list(header_components)),
            table_component,
            pagination_component,
        )

        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    async def _fetch_detail_data(self, pk: str | int) -> BaseModel | None:
        """Fetch a single row by primary key.

        Returns:
            Validated row data, or None if missing.
        """
        async with self._get_session_maker()() as session:
            pk_column = sa_inspect(self.model).columns[self._pk_name]
            stmt = sa_select(self.model).where(pk_column == pk)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                return None

            # Convert inside session to avoid detached instance access
            pydantic_model = self._get_pydantic_model()
            return pydantic_model.model_validate(item, from_attributes=True)

    async def _detail_api(self, request: Request) -> JSONResponse:
        """Return detail view components.

        Returns:
            JSON response with FastUI components.
        """
        pk = cast("str | int", request.path_params["pk"])

        try:
            data = await self._fetch_detail_data(pk)
        except SQLAlchemyError:
            logger.exception("Error loading %s #%s", self.name, pk)
            return self._error_response(
                _LOAD_ERROR.format(name=self.name), status_code=500
            )

        if data is None:
            return self._error_response(
                f"{self.name} with ID {pk} was not found.",
                back_url=f"{self.get_url()}/",
                status_code=404,
            )

        # Build action buttons
        action_components: list[c.AnyComponent] = [
            c.Link(
                components=[c.Text(text="← Back to List")],
                on_click=GoToEvent(url=f"{self.get_url()}/"),
                class_name="btn btn-secondary me-2",
            )
        ]

        if self.can_edit:
            action_components.append(
                c.Link(
                    components=[c.Text(text="Edit")],
                    on_click=GoToEvent(url="./edit"),
                    class_name="btn btn-primary me-2",
                )
            )

        if self.can_delete:
            action_components.append(
                c.ModelForm(
                    model=_DeleteConfirmModel,
                    submit_url="./delete",
                    method="POST",
                    footer=[c.Button(text="Delete", class_name="btn btn-danger")],
                )
            )

        components = self._admin.layout.render(
            c.Heading(text=f"{self.name} #{pk}", level=2),
            c.Div(components=list(action_components), class_name="mb-3"),
            c.Details(data=data),
        )

        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    async def _create_api(self, request: Request) -> JSONResponse:
        """Return create form or create a record.

        Returns:
            JSON response with FastUI components.
        """
        if request.method == "GET":
            form_model = self._get_form_model()

            components = self._admin.layout.render(
                c.Heading(text=f"Create {self.name}", level=2),
                c.Link(
                    components=[c.Text(text="← Back to List")],
                    on_click=GoToEvent(url=f"{self.get_url()}/"),
                    class_name="btn btn-secondary mb-3",
                ),
                c.ModelForm(model=form_model, submit_url="."),
            )

            return JSONResponse([
                comp.model_dump(mode="json", exclude_none=True) for comp in components
            ])

        # POST - Create new record
        raw_data = cast("object", await request.json())

        form_model = self._get_form_model()
        try:
            validated = form_model.model_validate(raw_data)
        except ValidationError as exc:
            logger.warning("Validation error creating %s: %s", self.name, exc)
            field_errors = "; ".join(
                f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
                for e in exc.errors()
            )
            return self._error_response(
                f"Invalid input: {field_errors}", back_url=".", status_code=422
            )

        async with self._get_session_maker()() as session:
            try:
                item = self.model(**validated.model_dump())
                session.add(item)
                await session.commit()
                await session.refresh(item)
                pk = cast("str | int", getattr(item, self._pk_name))
            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Error creating %s", self.name)
                return self._error_response(
                    f"Failed to create {self.name}. Check server logs for details.",
                    back_url=".",
                    status_code=500,
                )

        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/{pk}"))]
        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    async def _apply_update(self, pk: str | int, validated: BaseModel) -> bool:
        """Apply validated changes to a row.

        Returns:
            True if the row was updated, False if not found.
        """
        async with self._get_session_maker()() as session:
            pk_column = sa_inspect(self.model).columns[self._pk_name]
            stmt = sa_select(self.model).where(pk_column == pk)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                return False

            dumped: dict[str, object] = validated.model_dump()
            for key, value in dumped.items():
                setattr(item, key, value)
            await session.commit()
            return True

    async def _edit_api(self, request: Request) -> JSONResponse:
        """Return edit form or apply an update.

        Returns:
            JSON response with FastUI components.
        """
        pk = cast("str | int", request.path_params["pk"])
        form_model = self._get_form_model()

        if request.method == "GET":
            return await self._edit_api_get(pk, form_model)

        # POST - read body before opening a session
        raw_data = cast("object", await request.json())

        try:
            validated = form_model.model_validate(raw_data)
        except ValidationError as exc:
            logger.warning("Validation error updating %s #%s: %s", self.name, pk, exc)
            field_errors = "; ".join(
                f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
                for e in exc.errors()
            )
            return self._error_response(
                f"Invalid input: {field_errors}", back_url=".", status_code=422
            )

        try:
            updated = await self._apply_update(pk, validated)
        except SQLAlchemyError:
            logger.exception("Error updating %s #%s", self.name, pk)
            return self._error_response(
                f"Failed to update {self.name}. Check server logs for details.",
                back_url=".",
                status_code=500,
            )

        if not updated:
            return self._error_response(
                f"{self.name} with ID {pk} was not found.",
                back_url=f"{self.get_url()}/",
                status_code=404,
            )

        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/{pk}"))]
        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    async def _fetch_edit_initial(self, pk: str | int) -> dict[str, object] | None:
        """Fetch initial form data for an edit.

        Returns:
            Initial form data, or None if the row is missing.
        """
        async with self._get_session_maker()() as session:
            pk_column = sa_inspect(self.model).columns[self._pk_name]
            stmt = sa_select(self.model).where(pk_column == pk)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                return None

            pydantic_model = self._get_pydantic_model()
            return pydantic_model.model_validate(
                item, from_attributes=True
            ).model_dump()

    async def _edit_api_get(
        self, pk: str | int, form_model: type[BaseModel]
    ) -> JSONResponse:
        """Render the edit form for GET requests.

        Returns:
            JSON response with FastUI components.
        """
        try:
            initial_data = await self._fetch_edit_initial(pk)
        except SQLAlchemyError:
            logger.exception("Error loading %s #%s for edit", self.name, pk)
            return self._error_response(
                _LOAD_ERROR.format(name=self.name), status_code=500
            )

        if initial_data is None:
            return self._error_response(
                f"{self.name} with ID {pk} was not found.",
                back_url=f"{self.get_url()}/",
                status_code=404,
            )

        components = self._admin.layout.render(
            c.Heading(text=f"Edit {self.name} #{pk}", level=2),
            c.Link(
                components=[c.Text(text="← Back")],
                on_click=BackEvent(),
                class_name="btn btn-secondary mb-3",
            ),
            c.ModelForm(model=form_model, submit_url=".", initial=initial_data),
        )

        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    async def _delete_api(self, request: Request) -> JSONResponse:
        """Delete a record and redirect to the list.

        Returns:
            JSON response with FastUI components.
        """
        pk = cast("str | int", request.path_params["pk"])

        try:
            async with self._get_session_maker()() as session:
                item = await session.get(self.model, pk)
                if item is None:
                    return self._error_response(
                        f"{self.name} with ID {pk} was not found.",
                        back_url=f"{self.get_url()}/",
                        status_code=404,
                    )
                await session.delete(item)
                await session.commit()
        except SQLAlchemyError:
            logger.exception("Error deleting %s #%s", self.name, pk)
            return self._error_response(
                f"Failed to delete {self.name}. Check server logs for details.",
                back_url=f"{self.get_url()}/{pk}",
                status_code=500,
            )

        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/"))]
        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])
