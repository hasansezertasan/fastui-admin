import typing as _t

from pydantic import BaseModel


class BaseView(BaseModel):
    def __init__(
        self,
        name: _t.Union[str, None] = None,
        category: _t.Union[str, None] = None,
        endpoint: _t.Union[str, None] = None,
        url: _t.Union[str, None] = None,
    ) -> None:
        self.name = name
        self.category = category
        self.endpoint = endpoint
        self.url = url

    def get_endpoint(self) -> str: ...

    def get_view_url(self) -> str: ...

    def create_router(self) -> None: ...

    def is_visible(self) -> bool:
        return True

    def is_accessible(self) -> bool:
        return True


class AdminIndexView(BaseView): ...


class BaseModelView(BaseView): ...
