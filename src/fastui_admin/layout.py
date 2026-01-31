# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Layout system for FastUI Admin pages."""

from typing import TYPE_CHECKING, List, Literal, Optional, Union

from fastui import components as c
from fastui import prebuilt_html
from fastui.events import GoToEvent

if TYPE_CHECKING:
    from fastui_admin.base import BaseAdmin


class MasterLayout:
    """Layout manager for admin pages.

    Handles consistent page structure: navbar, content area, footer.
    """

    def __init__(
        self,
        title: str = "Admin",
        logo_url: Optional[str] = None,
    ):
        self.title = title
        self.logo_url = logo_url
        self._admin: Optional[BaseAdmin] = None

    def set_admin(self, admin: "BaseAdmin") -> None:
        """Set admin reference for navbar generation."""
        self._admin = admin

    def get_prebuilt_html(
        self,
        *,
        title: Optional[str] = None,
        api_root_url: Optional[str] = None,
        api_path_mode: Optional[Literal["append", "query"]] = None,
        api_path_strip: Optional[str] = None,
    ) -> str:
        """Get FastUI prebuilt HTML for serving the React frontend."""
        return prebuilt_html(
            title=title or self.title,
            api_root_url=api_root_url,
            api_path_mode=api_path_mode,
            api_path_strip=api_path_strip,
        )

    def page_title(self, text: Optional[str] = None) -> c.PageTitle:
        """Create page title component."""
        return c.PageTitle(text=text or self.title)

    def navbar(self) -> c.Navbar:
        """Build navigation bar with links to all visible views."""
        start_links: List[c.Link] = []

        if self._admin:
            for view in self._admin.views:
                if view.is_visible:
                    url = self._admin.get_relative_url(view.get_url())

                    start_links.append(
                        c.Link(
                            components=[c.Text(text=view.name)],
                            on_click=GoToEvent(url=url),
                            active=f"startswith:{url}" if url != "/" else url,
                        )
                    )

        return c.Navbar(
            title=self.title,
            title_event=GoToEvent(url="/"),
            start_links=start_links,
        )

    def footer(self) -> Union[c.Footer, c.Div]:
        """Build footer component."""
        return c.Footer(
            extra_text="Powered by FastUI Admin",
            links=[],
        )

    def page(self, *components: c.AnyComponent) -> c.Page:
        """Wrap components in a Page container."""
        return c.Page(components=list(components))

    def render(self, *components: c.AnyComponent) -> List[c.AnyComponent]:
        """Render full page with navbar, content, and footer.

        Returns a list of components ready to be serialized as JSON response.
        """
        return [
            self.page_title(),
            self.navbar(),
            self.page(*components),
            self.footer(),
        ]
