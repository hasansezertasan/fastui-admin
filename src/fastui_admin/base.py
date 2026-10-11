# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Core admin class for FastUI Admin.

Warning:
    FastUI Admin does NOT provide authentication, authorization, or CSRF protection.
    All admin endpoints are publicly accessible by default.
    Mutating endpoints (create/edit/delete) accept JSON POST without CSRF tokens.
    FastUI's fetch-based forms rely on browser same-origin policy, but XSS on the same
    domain can bypass this. You MUST add your own authentication middleware and consider
    CSRF protection before deploying to production.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from fastui_admin.layout import MasterLayout
from fastui_admin.utils import slugify

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
    from starlette.requests import Request

    from fastui_admin.views import AdminIndexView, BaseModelView, BaseView

__all__ = ["BaseAdmin"]


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

    # pylint: disable=too-many-instance-attributes  # config façade: one attr per option

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        app: FastAPI | Starlette,
        engine: AsyncEngine | None = None,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
        title: str = "Admin",
        base_url: str = "/admin",
        route_name: str = "admin",
        logo_url: str | None = None,
        index_view: type[AdminIndexView] | None = None,
        *,
        debug: bool = False,
    ) -> None:
        """Initialize the admin interface.

        Args:
            app: FastAPI or Starlette application to mount admin on.
            engine: Async SQLAlchemy engine. Sync engines are not supported.
            session_maker: Optional async session maker.
                If not provided, created from engine.
            title: Admin interface title.
            base_url: Base URL path for admin (default: "/admin").
            route_name: Name for the mounted admin route.
            logo_url: URL of logo image.
            index_view: Custom index view class.
            debug: Enable debug mode.

        Raises:
            TypeError: If neither engine nor session_maker is provided.
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

        self.app: FastAPI | Starlette = app
        self.engine: AsyncEngine | None = engine
        self.session_maker: async_sessionmaker[AsyncSession] = (
            session_maker or self._create_session_maker(engine)
        )

        self.title: str = title
        self.base_url: str = base_url.rstrip("/")
        self.route_name: str = route_name
        self.logo_url: str | None = logo_url
        self.debug: bool = debug

        self.layout: MasterLayout = MasterLayout(
            admin=self, title=title, logo_url=logo_url
        )

        self._views: list[BaseView] = []
        self._model_views: list[BaseModelView] = []

        self._index_view_class: type[AdminIndexView] | None = index_view
        self._mounted: bool = False

    @staticmethod
    def _validate_session_maker(session_maker: object) -> None:
        """Reject sync sessionmaker instances.

        Raises:
            TypeError: If session_maker is sync or of unrecognized type.
        """
        # Snapshot the name before isinstance narrowing: after narrowing, the
        # union carries partially-unknown generics that checkers flag in type().
        maker_name: str = type(session_maker).__name__
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

            if isinstance(session_maker, async_sessionmaker):
                return
        except ImportError:
            pass

        try:
            from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

            if isinstance(session_maker, sessionmaker):
                msg = (
                    "Sync sessionmaker is not supported. "
                    "Use async_sessionmaker from sqlalchemy.ext.asyncio instead."
                )
                raise TypeError(msg)
        except ImportError:
            pass

        msg = (
            f"Unrecognized session_maker type: {maker_name}. "
            "Expected async_sessionmaker from sqlalchemy.ext.asyncio."
        )
        raise TypeError(msg)

    @staticmethod
    def _create_session_maker(engine: object) -> async_sessionmaker[AsyncSession]:
        """Create async session maker from engine.

        Returns:
            New async session maker bound to engine.

        Raises:
            TypeError: If engine is None or not an async engine.
        """
        if engine is None:
            msg = "Cannot create session_maker: no engine provided."
            raise TypeError(msg)

        try:
            from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
                AsyncEngine,
                AsyncSession,
                async_sessionmaker,
            )

            if isinstance(engine, AsyncEngine):
                return async_sessionmaker(
                    engine, class_=AsyncSession, expire_on_commit=False
                )
        except ImportError:
            pass

        msg = (
            f"Engine of type {type(engine).__name__} is not a supported async engine. "
            "Use create_async_engine() from sqlalchemy.ext.asyncio."
        )
        raise TypeError(msg)

    def get_relative_url(self, url: str) -> str:
        """Strip base_url prefix to produce a relative path.

        Returns:
            Path relative to the admin mount point.
        """
        if self.base_url and url.startswith(self.base_url):
            return url[len(self.base_url) :] or "/"
        return url

    @property
    def views(self) -> Sequence[BaseView]:
        """All registered views (read-only for navbar)."""
        return list(self._views)

    def add_view(self, view: object) -> None:
        """Add a view to the admin interface.

        Args:
            view: View class to add (will be instantiated with admin reference).
                Typed as ``object`` because non-class arguments are validated
                at runtime (see Raises) rather than rejected by callers' checkers.

        Raises:
            RuntimeError: If called after mount().
            TypeError: If view is not a BaseView subclass.
        """
        if self._mounted:
            msg = "Cannot add views after mount() has been called."
            raise RuntimeError(msg)

        from fastui_admin.views import BaseModelView, BaseView  # noqa: PLC0415

        # Snapshot the name before isinstance narrowing (see _validate_session_maker).
        view_name: str = type(view).__name__
        if not isinstance(view, type) or not issubclass(view, BaseView):
            msg = (
                f"add_view() expects a BaseView subclass, got {view_name}. "
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

        admin_app = Starlette(debug=self.debug, routes=routes)

        if isinstance(self.app, FastAPI):
            self.app.mount(self.base_url, admin_app, name=self.route_name)
        else:
            self.app.routes.append(
                Mount(self.base_url, app=admin_app, name=self.route_name)
            )

        self._mounted = True

    def _build_routes(self) -> list[Route]:
        """Build all routes for admin interface.

        Returns:
            List of routes for the admin interface.
        """
        routes: list[Route] = []

        routes.extend((
            Route("/", endpoint=self._index_html, name="index"),
            Route("/api/", endpoint=self._index_api, name="index_api"),
        ))

        for view in self._model_views:
            routes.extend(view.get_routes())

        from fastui_admin.views import AdminIndexView, BaseModelView  # noqa: PLC0415

        for base_view in self._views:
            if isinstance(base_view, (AdminIndexView, BaseModelView)):
                continue
            view_slug = slugify(base_view.name)
            view_name = base_view.name
            routes.extend((
                Route(
                    f"/{view_slug}/",
                    endpoint=self._make_view_html(base_view),
                    name=f"{view_name}_html",
                ),
                Route(
                    f"/api/{view_slug}/",
                    endpoint=self._make_view_api(base_view),
                    name=f"{view_name}_api",
                ),
            ))

        routes.append(
            Route("/{path:path}", endpoint=self._catch_all_html, name="catch_all")
        )

        return routes

    async def _index_html(self, _request: Request) -> HTMLResponse:
        """Serve the SPA shell for index page.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self.layout.get_prebuilt_html(
                title=self.title, api_root_url=f"{self.base_url}/api"
            )
        )

    async def _index_api(self, request: Request) -> JSONResponse:
        """Return index page components.

        The index view is always present — mount() inserts it at _views[0].

        Returns:
            JSON response with FastUI components.
        """
        index_view = self._views[0]
        components = await index_view.render(request)
        return JSONResponse([
            comp.model_dump(mode="json", exclude_none=True) for comp in components
        ])

    def _make_view_html(
        self, view: BaseView
    ) -> Callable[[Request], Awaitable[HTMLResponse]]:
        """Create an HTML endpoint for a plain BaseView.

        Returns:
            Async endpoint serving the SPA shell.
        """

        async def endpoint(_request: Request) -> HTMLResponse:  # noqa: RUF029
            return HTMLResponse(
                self.layout.get_prebuilt_html(
                    title=f"{view.name} - {self.title}",
                    api_root_url=f"{self.base_url}/api",
                )
            )

        return endpoint

    @staticmethod
    def _make_view_api(view: BaseView) -> Callable[[Request], Awaitable[JSONResponse]]:
        """Create an API endpoint for a plain BaseView.

        Returns:
            Async endpoint returning FastUI components.
        """

        async def endpoint(request: Request) -> JSONResponse:
            components = await view.render(request)
            return JSONResponse([
                comp.model_dump(mode="json", exclude_none=True) for comp in components
            ])

        return endpoint

    async def _catch_all_html(self, _request: Request) -> HTMLResponse:
        """Catch-all endpoint for SPA routing.

        Returns:
            HTML response with the prebuilt admin shell.
        """
        return HTMLResponse(
            self.layout.get_prebuilt_html(
                title=self.title, api_root_url=f"{self.base_url}/api"
            )
        )
