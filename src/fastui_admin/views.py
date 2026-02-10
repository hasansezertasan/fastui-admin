# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""View classes for FastUI Admin."""

import logging
from typing import TYPE_CHECKING, Any, ClassVar, List, Optional, Type

from fastui import components as c
from fastui.components.display import DisplayLookup
from fastui.events import BackEvent, GoToEvent
from pydantic import BaseModel, ValidationError, create_model
from sqlalchemy import func as sa_func
from sqlalchemy import select as sa_select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect as sa_inspect
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from fastui_admin.utils import sqlalchemy_to_pydantic

logger = logging.getLogger(__name__)

# Cached empty model for delete confirmation forms
_DeleteConfirmModel = create_model("DeleteConfirm")

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase

    from fastui_admin.base import BaseAdmin


class BaseView:
    """Base class for all admin views.

    Provides common functionality for visibility, URL generation, and rendering.
    """

    # View metadata (override in subclasses)
    name: ClassVar[str] = ""
    category: ClassVar[Optional[str]] = None
    icon: ClassVar[Optional[str]] = None
    is_visible: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Set default name from class name if not explicitly provided."""
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("name"):
            cls.name = cls.__name__

    def __init__(self, admin: "BaseAdmin"):
        """Initialize view with admin reference.

        Args:
            admin: The BaseAdmin instance this view belongs to.
        """
        self._admin = admin

    @property
    def admin(self) -> "BaseAdmin":
        """Get the admin instance."""
        return self._admin

    def get_url(self) -> str:
        """Get the URL for this view."""
        return f"{self._admin.base_url}/{self.name.lower().replace(' ', '-')}"

    async def render(self, request: Request) -> List[c.AnyComponent]:  # noqa: ARG002
        """Render view components. Override in subclasses."""
        return []


class AdminIndexView(BaseView):
    """Default index/dashboard view for the admin interface."""

    name: ClassVar[str] = "Dashboard"
    icon: ClassVar[str] = "home"

    def get_url(self) -> str:
        """Index view is at root."""
        return self._admin.base_url

    async def render(self, request: Request) -> List[c.AnyComponent]:  # noqa: ARG002
        """Render dashboard with welcome message and links to model views."""
        # Build links to all model views
        model_links = []
        for view in self._admin.views:
            if view.is_visible and view != self and hasattr(view, "model"):
                url = self._admin.get_relative_url(view.get_url())

                model_links.append(
                    c.Link(
                        components=[c.Text(text=f"{view.name}")],
                        on_click=GoToEvent(url=url),
                        class_name="btn btn-outline-primary me-2 mb-2",
                    )
                )

        page_components: List[c.AnyComponent] = [
            c.Heading(text=f"Welcome to {self._admin.title}", level=2),
            c.Paragraph(text="Select a model from the navigation to manage your data."),
        ]

        if model_links:
            page_components.append(c.Div(components=list(model_links), class_name="mt-3"))

        return self._admin.layout.render(*page_components)


class BaseModelView(BaseView):
    """View for SQLAlchemy model CRUD operations.

    Usage:
        ```python
        class UserAdmin(BaseModelView, model=User):
            name = "Users"
            column_list = ["id", "username", "email"]
            page_size = 25
        ```
    """

    # Model configuration (set via __init_subclass__)
    model: ClassVar[Type["DeclarativeBase"]]

    # List view configuration
    column_list: ClassVar[Optional[List[str]]] = None  # None = all columns
    column_exclude_list: ClassVar[List[str]] = []
    page_size: ClassVar[int] = 25

    # Permissions
    can_create: ClassVar[bool] = True
    can_edit: ClassVar[bool] = True
    can_delete: ClassVar[bool] = True
    can_view_details: ClassVar[bool] = True

    def __init_subclass__(cls, model: Optional[Type["DeclarativeBase"]] = None, **kwargs: Any) -> None:
        """Capture model from class definition syntax.

        Allows: class UserAdmin(BaseModelView, model=User)
        Also sets a default name from the model's table name if not explicitly provided.
        """
        super().__init_subclass__(**kwargs)
        if model is not None:
            cls.model = model
            # Set default name from model if not explicitly set on this class
            if "name" not in cls.__dict__:
                cls.name = str(getattr(model, "__tablename__", model.__name__)).title()

    def __init__(self, admin: "BaseAdmin"):
        """Initialize model view."""
        super().__init__(admin)

        # Cache model metadata
        self._pk_name = self._get_pk_name()
        self._pydantic_model: Optional[Type[BaseModel]] = None
        self._form_model: Optional[Type[BaseModel]] = None

    def _get_pk_name(self) -> str:
        """Get primary key column name."""
        mapper = sa_inspect(self.model)
        if mapper.primary_key:
            return str(mapper.primary_key[0].name)
        msg = f"Model {self.model.__name__} has no primary key"
        raise ValueError(msg)

    def _get_columns(self) -> List[str]:
        """Get list of column names for list view."""
        mapper = sa_inspect(self.model)
        all_columns = [col.key for col in mapper.columns]

        if self.column_list:
            return [col for col in self.column_list if col in all_columns]

        return [col for col in all_columns if col not in self.column_exclude_list]

    def _get_pydantic_model(self) -> Type[BaseModel]:
        """Get or create Pydantic model for this SQLAlchemy model."""
        if self._pydantic_model is None:
            self._pydantic_model = sqlalchemy_to_pydantic(
                self.model,
                include_columns=self._get_columns(),
            )
        return self._pydantic_model

    def _get_form_model(self) -> Type[BaseModel]:
        """Get Pydantic model for forms (excludes PK)."""
        if self._form_model is None:
            columns = self._get_columns()
            # Exclude primary key for forms
            columns = [col for col in columns if col != self._pk_name]

            self._form_model = sqlalchemy_to_pydantic(
                self.model,
                include_columns=columns,
            )
        return self._form_model

    def get_url(self) -> str:
        """Get base URL for this model view."""
        table_name = getattr(self.model, "__tablename__", self.model.__name__.lower())
        return f"{self._admin.base_url}/{table_name}"

    def get_routes(self) -> List[Route]:
        """Get all routes for this model view."""
        table_name = getattr(self.model, "__tablename__", self.model.__name__.lower())
        base = f"/{table_name}"

        routes = [
            # List view
            Route(f"{base}/", endpoint=self._list_html, name=f"{self.name}_list"),
            Route(f"/api{base}/", endpoint=self._list_api, name=f"{self.name}_list_api"),
        ]

        if self.can_create:
            routes.extend(
                [
                    Route(f"{base}/create", endpoint=self._create_html, name=f"{self.name}_create"),
                    Route(
                        f"/api{base}/create",
                        endpoint=self._create_api,
                        methods=["GET", "POST"],
                        name=f"{self.name}_create_api",
                    ),
                ]
            )

        if self.can_view_details:
            routes.extend(
                [
                    Route(f"{base}/{{pk:int}}", endpoint=self._detail_html, name=f"{self.name}_detail"),
                    Route(f"/api{base}/{{pk:int}}", endpoint=self._detail_api, name=f"{self.name}_detail_api"),
                ]
            )

        if self.can_edit:
            routes.extend(
                [
                    Route(f"{base}/{{pk:int}}/edit", endpoint=self._edit_html, name=f"{self.name}_edit"),
                    Route(
                        f"/api{base}/{{pk:int}}/edit",
                        endpoint=self._edit_api,
                        methods=["GET", "POST"],
                        name=f"{self.name}_edit_api",
                    ),
                ]
            )

        if self.can_delete:
            routes.append(
                Route(
                    f"/api{base}/{{pk:int}}/delete",
                    endpoint=self._delete_api,
                    methods=["POST"],
                    name=f"{self.name}_delete_api",
                )
            )

        return routes

    def _error_response(self, message: str, back_url: Optional[str] = None) -> JSONResponse:
        """Return a JSON response rendering an error page in the admin UI."""
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
            status_code=400,
        )

    # --- HTML Endpoints (serve React frontend) ---

    async def _list_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Serve frontend HTML for list view."""
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"{self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _detail_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Serve frontend HTML for detail view."""
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"{self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _create_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Serve frontend HTML for create view."""
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"Create {self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    async def _edit_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Serve frontend HTML for edit view."""
        return HTMLResponse(
            self._admin.layout.get_prebuilt_html(
                title=f"Edit {self.name} - {self._admin.title}",
                api_root_url=f"{self._admin.base_url}/api",
            )
        )

    # --- API Endpoints (return FastUI components as JSON) ---

    def _get_session_maker(self) -> Any:
        """Get session maker, raising if not configured."""
        sm = self._admin.session_maker
        if sm is None:
            msg = "No session maker configured. Provide engine or session_maker to BaseAdmin."
            raise RuntimeError(msg)
        return sm

    async def _list_api(self, request: Request) -> JSONResponse:
        """API endpoint returning list view components."""
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        page_size = self.page_size

        async with self._get_session_maker()() as session:
            # Count total records
            count_stmt = sa_select(sa_func.count()).select_from(self.model)
            total = (await session.execute(count_stmt)).scalar() or 0

            # Fetch page of records
            stmt = sa_select(self.model).offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            items = result.scalars().all()

        # Convert to Pydantic for FastUI
        pydantic_model = self._get_pydantic_model()
        data = [pydantic_model.model_validate(item, from_attributes=True) for item in items]

        # Build table columns
        columns = []
        for col_name in self._get_columns():
            col = DisplayLookup(field=col_name)
            # Make PK clickable to detail view
            if col_name == self._pk_name and self.can_view_details:
                col = DisplayLookup(
                    field=col_name,
                    on_click=GoToEvent(url=f"./{{{self._pk_name}}}"),
                )
            columns.append(col)

        # Build page components
        header_components: List[c.AnyComponent] = [c.Heading(text=self.name, level=2)]

        if self.can_create:
            header_components.append(
                c.Link(
                    components=[c.Text(text=f"+ Create New {self.name}")],
                    on_click=GoToEvent(url="./create"),
                    class_name="btn btn-primary mb-3",
                )
            )

        table_component = c.Table(
            data=data,
            data_model=pydantic_model,
            columns=columns,
        )

        pagination_component = c.Pagination(
            page=page,
            page_size=page_size,
            total=total,
        )

        components = self._admin.layout.render(
            c.Div(components=list(header_components)),
            table_component,
            pagination_component,
        )

        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

    async def _detail_api(self, request: Request) -> JSONResponse:
        """API endpoint returning detail view components."""
        pk = request.path_params["pk"]

        async with self._get_session_maker()() as session:
            stmt = sa_select(self.model).where(getattr(self.model, self._pk_name) == pk)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

        if not item:
            return JSONResponse({"detail": "Not found"}, status_code=404)

        # Convert to Pydantic for display
        pydantic_model = self._get_pydantic_model()
        data = pydantic_model.model_validate(item, from_attributes=True)

        # Build action buttons
        action_components: List[c.AnyComponent] = [
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
            # Use a form to POST to the delete endpoint
            action_components.append(
                c.ModelForm(
                    model=_DeleteConfirmModel,
                    submit_url=f"./{pk}/delete",
                    method="POST",
                    footer=[
                        c.Button(text="Delete", class_name="btn btn-danger"),
                    ],
                )
            )

        components = self._admin.layout.render(
            c.Heading(text=f"{self.name} #{pk}", level=2),
            c.Div(components=list(action_components), class_name="mb-3"),
            c.Details(data=data),
        )

        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

    async def _create_api(self, request: Request) -> JSONResponse:
        """API endpoint for create form (GET) and create action (POST)."""
        if request.method == "GET":
            # Show create form
            form_model = self._get_form_model()

            components = self._admin.layout.render(
                c.Heading(text=f"Create {self.name}", level=2),
                c.Link(
                    components=[c.Text(text="← Back to List")],
                    on_click=GoToEvent(url=f"{self.get_url()}/"),
                    class_name="btn btn-secondary mb-3",
                ),
                c.ModelForm(
                    model=form_model,
                    submit_url=".",
                ),
            )

            return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

        # POST - Create new record
        raw_data = await request.json()

        # Validate through Pydantic form model
        form_model = self._get_form_model()
        try:
            validated = form_model.model_validate(raw_data)
        except ValidationError as exc:
            logger.warning("Validation error creating %s: %s", self.name, exc)
            return self._error_response("Invalid input. Please check the form values and try again.", back_url=".")

        async with self._get_session_maker()() as session:
            try:
                item = self.model(**validated.model_dump())
                session.add(item)
                await session.commit()
                await session.refresh(item)
                pk = getattr(item, self._pk_name)
            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Error creating %s", self.name)
                return self._error_response(
                    f"Failed to create {self.name}. Check server logs for details.", back_url="."
                )

        # Return redirect to detail view
        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/{pk}"))]
        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

    async def _edit_api(self, request: Request) -> JSONResponse:
        """API endpoint for edit form (GET) and update action (POST)."""
        pk = request.path_params["pk"]

        async with self._get_session_maker()() as session:
            stmt = sa_select(self.model).where(getattr(self.model, self._pk_name) == pk)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                return JSONResponse({"detail": "Not found"}, status_code=404)

            if request.method == "GET":
                # Show edit form with current values
                form_model = self._get_form_model()
                pydantic_model = self._get_pydantic_model()
                initial_data = pydantic_model.model_validate(item, from_attributes=True).model_dump()

                components = self._admin.layout.render(
                    c.Heading(text=f"Edit {self.name} #{pk}", level=2),
                    c.Link(
                        components=[c.Text(text="← Back")],
                        on_click=BackEvent(),
                        class_name="btn btn-secondary mb-3",
                    ),
                    c.ModelForm(
                        model=form_model,
                        submit_url=".",
                        initial=initial_data,
                    ),
                )

                return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

            # POST - Update record
            raw_data = await request.json()

            # Validate through Pydantic form model
            form_model = self._get_form_model()
            try:
                validated = form_model.model_validate(raw_data)
            except ValidationError as exc:
                logger.warning("Validation error updating %s #%s: %s", self.name, pk, exc)
                return self._error_response("Invalid input. Please check the form values and try again.", back_url=".")

            try:
                for key, value in validated.model_dump().items():
                    setattr(item, key, value)
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                logger.exception("Error updating %s #%s", self.name, pk)
                return self._error_response(
                    f"Failed to update {self.name}. Check server logs for details.", back_url="."
                )

        # Return redirect to detail view
        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/{pk}"))]
        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

    async def _delete_api(self, request: Request) -> JSONResponse:
        """API endpoint for delete action."""
        pk = request.path_params["pk"]

        try:
            async with self._get_session_maker()() as session:
                item = await session.get(self.model, pk)
                if item is None:
                    return JSONResponse({"detail": "Not found"}, status_code=404)
                await session.delete(item)
                await session.commit()
        except SQLAlchemyError:
            logger.exception("Error deleting %s #%s", self.name, pk)
            return self._error_response(
                f"Failed to delete {self.name}. Check server logs for details.", back_url=f"{self.get_url()}/{pk}"
            )

        # Return redirect to list view
        components = [c.FireEvent(event=GoToEvent(url=f"{self.get_url()}/"))]
        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])
