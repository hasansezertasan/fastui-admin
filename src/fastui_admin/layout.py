import typing as _t

from fastui import components as c
from fastui import prebuilt_html


class MasterLayout:
    def __init__(self, title: _t.Union[str, None] = None):
        self.title = title or "Admin"

    def prebuilt_html(
        self,
        *,
        title: _t.Union[str, None] = None,
        api_root_url: _t.Union[str, None] = None,
        api_path_mode: _t.Union[_t.Literal["append", "query"], None] = None,
        api_path_strip: _t.Union[str, None] = None,
    ) -> str:
        return prebuilt_html(
            title=title or self.title,
            api_root_url=api_root_url,
            api_path_mode=api_path_mode,
            api_path_strip=api_path_strip,
        )

    def page_title(self, text: str):
        return c.PageTitle(text=text)

    def navbar(self): ...
    def footer(self): ...

    def page(self, *components: c.AnyComponent):
        return c.Page(components=components)

    def render(self, *components: c.AnyComponent):
        return [
            self.page_title(self.title),
            self.navbar(),
            self.page(*components),
            self.footer(),
        ]
