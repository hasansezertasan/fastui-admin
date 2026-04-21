# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Core admin class for FastUI Admin.

Warning:
    FastUI Admin does NOT provide authentication or authorization.
    All admin endpoints are publicly accessible by default.
    You MUST add your own authentication middleware before deploying to production.
"""

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from fastui_admin.layout import MasterLayout
from fastui_admin.utils import slugify

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from fastui_admin.views import AdminIndexView, BaseModelView, BaseView

logger = logging.getLogger(__name__)


class BaseAdmin:
    """Base class for implementing Admin interface.

    Warning:
        This admin interface has NO built-in authentication.
        All CRUD endpoints are publicly accessible. Add authentication
        middleware before deploying to production.

    Example:
        ```python
        from fastapi import FastAPI
        from sqlalchemy.ext.asyncio import create_async_engine

        from fastui_admin import BaseAdmin, BaseModelView

        app = FastAPI()
        engine = create_async_engine("sqlite+aiosqlite:///./db.sqlite")

        class UserAdmin(BaseModelView, model=User):
            name = "Users"
            column_list = ["id", "username", "email"]

        admin = BaseAdmin(app, engine, title="My Admin")
        admin.add_view(UserAdmin)
        admin.mount()
        ```
    """

    def __init__(
        self,
        app: Union[FastAPI, Starlette],
        engine: Optional["AsyncEngine"] = None,
        session_maker: Optional["async_sessionmaker[AsyncSession]"] = None,
        title: str = "Admin",
        base_url: str = "/admin",
        route_name: str = "admin",
        logo_url: Optional[str] = None,
        index_view: Optional[type["AdminIndexView"]] = None,
        debug: bool = False,
    ):
        """Initialize the admin interface.

        Args:
            app: FastAPI or Starlette application to mount admin on.
            engine: Async SQLAlchemy engine. Sync engines are not supported.
            session_maker: Optional async session maker. If not provided, created from engine.
            title: Admin interface title.
            base_url: Base URL path for admin (default: "/admin").
            route_name: Name for the mounted admin route.
            logo_url: URL of logo image.
            index_view: Custom index view class.
            debug: Enable debug mode.
        """
        if engine is None and session_maker is None:
            msg = (
                "Neither engine nor session_maker provided. "
                "All database-backed model views will raise RuntimeError. "
                "Pass an async engine or session_maker to BaseAdmin."
            )
            raise TypeError(msg)

        if session_maker is not None:
            self._validate_session_maker(session_maker)

        self.app = app
        self.engine = engine
        self.session_maker: async_sessionmaker[AsyncSession] = session_maker or self._create_session_maker(engine)

        self.title = title
        self.base_url = base_url.rstrip("/")
        self.route_name = route_name
        self.logo_url = logo_url
        self.debug = debug

        self.layout = MasterLayout(admin=self, title=title, logo_url=logo_url)

        self._views: list[BaseView] = []
        self._model_views: list[BaseModelView] = []

        self._index_view_class = index_view
        self._mounted = False

    @staticmethod
    def _validate_session_maker(session_maker: Any) -> None:
        """Reject sync sessionmaker instances. Unrecognized types raise TypeError."""
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

            if isinstance(session_maker, async_sessionmaker):
                return
        except ImportError:
            pass

        try:
            from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

            if isinstance(session_maker, sessionmaker):
                msg = "Sync sessionmaker is not supported. Use async_sessionmaker from sqlalchemy.ext.asyncio instead."
                raise TypeError(msg)
        except ImportError:
            pass

        msg = (
            f"Unrecognized session_maker type: {type(session_maker).__name__}. "
            "Expected async_sessionmaker from sqlalchemy.ext.asyncio."
        )
        raise TypeError(msg)

    def _create_session_maker(self, engine: Optional["AsyncEngine"]) -> "async_sessionmaker[AsyncSession]":
        """Create async session maker from engine."""
        if engine is None:
            msg = "Cannot create session_maker: no engine provided."
            raise TypeError(msg)

        try:
            from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker  # noqa: PLC0415

            if isinstance(engine, AsyncEngine):
                return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        except ImportError:
            pass

        msg = (
            f"Engine of type {type(engine).__name__} is not a supported async engine. "
            "Use create_async_engine() from sqlalchemy.ext.asyncio."
        )
        raise TypeError(msg)

    def get_relative_url(self, url: str) -> str:
        """Strip the base_url path prefix to produce a path relative to the admin mount point."""
        if self.base_url and url.startswith(self.base_url):
            return url[len(self.base_url) :] or "/"
        return url

    @property
    def views(self) -> Sequence["BaseView"]:
        """All registered views (read-only for navbar)."""
        return list(self._views)

    def add_view(self, view: Union[type["BaseView"], type["BaseModelView"]]) -> None:
        """Add a view to the admin interface.

        Args:
            view: View class to add (will be instantiated with admin reference).

        Raises:
            RuntimeError: If called after mount().
            TypeError: If view is not a BaseView subclass.
        """
        if self._mounted:
            msg = "Cannot add views after mount() has been called."
            raise RuntimeError(msg)

        from fastui_admin.views import BaseModelView, BaseView  # noqa: PLC0415

        if not isinstance(view, type) or not issubclass(view, BaseView):
            msg = (
                f"add_view() expects a BaseView subclass, got {type(view).__name__}. "
                "Pass the class itself, not an instance."
            )
            raise TypeError(msg)

        if issubclass(view, BaseModelView):
            model_instance = view(admin=self)
            self._model_views.append(model_instance)
            self._views.append(model_instance)
        else:
            base_instance = view(admin=self)
            self._views.append(base_instance)

    def mount(self) -> None:
        """Mount the admin interface to the application.

        This should be called after all views are added.
        """
        if self._mounted:
            logger.debug("Admin already mounted, skipping.")
            return

        from fastui_admin.views import AdminIndexView  # noqa: PLC0415

        index_class = self._index_view_class or AdminIndexView
        index_instance = index_class(admin=self)
        self._views.insert(0, index_instance)

        routes = self._build_routes()

        admin_app = Starlette(
            debug=self.debug,
            routes=routes,
        )

        if isinstance(self.app, FastAPI):
            self.app.mount(self.base_url, admin_app, name=self.route_name)
        else:
            self.app.routes.append(Mount(self.base_url, app=admin_app, name=self.route_name))

        self._mounted = True

    def _build_routes(self) -> list[Route]:
        """Build all routes for admin interface."""
        routes: list[Route] = []

        routes.append(Route("/", endpoint=self._index_html, name="index"))
        routes.append(Route("/api/", endpoint=self._index_api, name="index_api"))

        for view in self._model_views:
            routes.extend(view.get_routes())

        from fastui_admin.views import AdminIndexView, BaseModelView  # noqa: PLC0415

        for base_view in self._views:
            if isinstance(base_view, (AdminIndexView, BaseModelView)):
                continue
            view_slug = slugify(base_view.name)
            view_name = base_view.name
            routes.append(Route(f"/{view_slug}/", endpoint=self._make_view_html(base_view), name=f"{view_name}_html"))
            routes.append(Route(f"/api/{view_slug}/", endpoint=self._make_view_api(base_view), name=f"{view_name}_api"))

        routes.append(Route("/{path:path}", endpoint=self._catch_all_html, name="catch_all"))

        return routes

    async def _index_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Serve the SPA shell for index page."""
        return HTMLResponse(
            self.layout.get_prebuilt_html(
                title=self.title,
                api_root_url=f"{self.base_url}/api",
            )
        )

    async def _index_api(self, request: Request) -> JSONResponse:
        """API endpoint returning index page components."""
        index_view = self._views[0] if self._views else None
        if index_view:
            components = await index_view.render(request)
            return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

        from fastui import components as c  # noqa: PLC0415

        components = self.layout.render(
            c.Heading(text=f"Welcome to {self.title}", level=2),
            c.Paragraph(text="Select a model from the navigation."),
        )
        return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

    def _make_view_html(self, view: "BaseView") -> Callable[..., Any]:
        """Create an HTML endpoint for a plain BaseView."""

        async def endpoint(request: Request) -> HTMLResponse:  # noqa: ARG001
            return HTMLResponse(
                self.layout.get_prebuilt_html(
                    title=f"{view.name} - {self.title}",
                    api_root_url=f"{self.base_url}/api",
                )
            )

        return endpoint

    def _make_view_api(self, view: "BaseView") -> Callable[..., Any]:
        """Create an API endpoint for a plain BaseView."""

        async def endpoint(request: Request) -> JSONResponse:
            components = await view.render(request)
            return JSONResponse([comp.model_dump(mode="json", exclude_none=True) for comp in components])

        return endpoint

    async def _catch_all_html(self, request: Request) -> HTMLResponse:  # noqa: ARG002
        """Catch-all endpoint for SPA routing."""
        return HTMLResponse(
            self.layout.get_prebuilt_html(
                title=self.title,
                api_root_url=f"{self.base_url}/api",
            )
        )
