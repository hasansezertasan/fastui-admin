from typing import List, Optional, Type, Union

from starlette.applications import Starlette
from starlette.routing import Mount, Route

from fastui_admin.views import AdminIndexView, BaseModelView, BaseView


class BaseAdmin:
    """Base class for implementing Admin interface."""

    def __init__(
        self,
        title: str = "Admin",
        base_url: str = "/admin",
        route_name: str = "admin",
        logo_url: Optional[str] = None,
        login_logo_url: Optional[str] = None,
        favicon_url: Optional[str] = None,
        index_view: Optional[AdminIndexView] = None,
        debug: bool = False,
    ):
        """
        Parameters:
            title: Admin title.
            base_url: Base URL for Admin interface.
            route_name: Mounted Admin name
            logo_url: URL of logo to be displayed instead of title.
            login_logo_url: If set, it will be used for login interface instead of logo_url.
            statics_dir: Statics dir for customisation
            index_view: CustomView to use for index page.
            favicon_url: URL of favicon.
        """
        # Set Dynamic Attributes
        self.title = title
        self.base_url = base_url
        self.route_name = route_name
        self.logo_url = logo_url
        self.login_logo_url = login_logo_url
        self.favicon_url = favicon_url
        self.index_view = index_view if (index_view is not None) else AdminIndexView("Home", name=self.route_name)
        # Set Static Attributes
        self.debug = debug
        self.views: List[BaseView] = []
        self.views.append(self.index_view)
        self._models: List[BaseModelView] = []
        self.routes: List[Union[Route, Mount]] = []

    def add_view(self, view: Union[Type[BaseView], BaseView]) -> None:
        """
        Add View to the Admin interface.
        """
        self._views.append(view)

    def prepare_admin_app(self) -> None:
        """
        Prepare Admin app by creating routes and views.
        """
        app = Starlette(
            debug=self.debug,
            routes=self.routes,
        )
        return app
