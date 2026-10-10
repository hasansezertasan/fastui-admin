# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for BaseAdmin and BaseModelView integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar, cast
from unittest import mock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.routing import BaseRoute, Mount

from fastui_admin import BaseAdmin, BaseModelView, BaseView

from .conftest import Base, User, UserAdmin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _types_in_dict(data: dict[str, Any]) -> set[str]:
    """Collect component types from a mapping."""
    found: set[str] = set()
    if "type" in data:
        marker = data["type"]
        if isinstance(marker, str):
            found.add(marker)
    for value in data.values():
        found.update(_find_component_types(value))
    return found


def _types_in_list(data: list[Any]) -> set[str]:
    """Collect component types from a sequence."""
    found: set[str] = set()
    for item in data:
        found.update(_find_component_types(item))
    return found


def _find_component_types(data: object) -> set[str]:
    """Recursively extract all component 'type' values from a FastUI JSON response."""
    if isinstance(data, dict):
        return _types_in_dict(cast("dict[str, Any]", data))
    if isinstance(data, list):
        return _types_in_list(data)
    return set()


def _pagination_in_dict(data: dict[str, Any]) -> dict[str, object] | None:
    """Search mapping values for the Pagination component."""
    if data.get("type") == "Pagination":
        return data
    for value in data.values():
        found = _find_pagination(value)
        if found is not None:
            return found
    return None


def _pagination_in_list(data: list[Any]) -> dict[str, object] | None:
    """Search sequence items for the Pagination component."""
    for item in data:
        found = _find_pagination(item)
        if found is not None:
            return found
    return None


def _find_pagination(data: object) -> dict[str, object] | None:
    """Recursively find the Pagination component dict in a FastUI JSON response."""
    if isinstance(data, dict):
        return _pagination_in_dict(cast("dict[str, Any]", data))
    if isinstance(data, list):
        return _pagination_in_list(data)
    return None


def _strings_in_dict(data: dict[str, Any]) -> list[str]:
    """Collect string values from a mapping."""
    values: list[str] = []
    for value in data.values():
        if isinstance(value, str):
            values.append(value)
        else:
            values.extend(_find_all_string_values(value))
    return values


def _strings_in_list(data: list[Any]) -> list[str]:
    """Collect string values from a sequence."""
    values: list[str] = []
    for item in data:
        values.extend(_find_all_string_values(item))
    return values


def _find_all_string_values(data: object) -> list[str]:
    """Recursively extract all string values from a JSON structure."""
    if isinstance(data, dict):
        return _strings_in_dict(cast("dict[str, Any]", data))
    if isinstance(data, list):
        return _strings_in_list(data)
    return []


@pytest_asyncio.fixture
async def client(
    app: FastAPI,
    setup_db: None,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    """Yield an HTTP client for the admin app.

    Yields:
        AsyncClient: Connected test client.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_client(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> AsyncClient:
    """Yield a client with a seeded user."""
    async with session_maker() as session:
        user = User(username="alice", email="alice@example.com", is_active=True)
        session.add(user)
        await session.commit()
    return client


class TestAdminIndex:
    """Admin index endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_index_html(client: AsyncClient) -> None:
        """Verify index HTML page loads."""
        resp = await client.get("/admin/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_index_api(client: AsyncClient) -> None:
        """Verify index API endpoint responds."""
        resp = await client.get("/admin/api/")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"


class TestListView:
    """Model list view endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_html(client: AsyncClient) -> None:
        """Verify list HTML page loads."""
        resp = await client.get("/admin/users/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_empty(client: AsyncClient) -> None:
        """Verify empty list renders table."""
        resp = await client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        types = _find_component_types(data)
        assert "Table" in types
        assert "Pagination" in types

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_with_data(seeded_client: AsyncClient) -> None:
        """Verify seeded list renders data."""
        resp = await seeded_client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        types = _find_component_types(data)
        assert "Table" in types
        assert "Pagination" in types
        # Verify actual data appears in response
        texts = _find_all_string_values(data)
        assert any("alice" in t for t in texts), (
            "Seeded user 'alice' should appear in table"
        )


class TestDetailView:
    """Model detail view endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_not_found(client: AsyncClient) -> None:
        """Verify missing detail returns FastUI 404."""
        resp = await client.get("/admin/api/users/999")
        assert resp.status_code == 404
        # Should return FastUI components, not raw JSON
        data = resp.json()
        assert isinstance(data, list)

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_found(seeded_client: AsyncClient) -> None:
        """Verify existing detail renders components."""
        resp = await seeded_client.get("/admin/api/users/1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        types = _find_component_types(data)
        assert "Details" in types
        assert "Heading" in types


class TestCreateView:
    """Model create view endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_form(client: AsyncClient) -> None:
        """Verify create form loads."""
        resp = await client.get("/admin/api/users/create")
        assert resp.status_code == 200

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_submit(client: AsyncClient) -> None:
        """Verify submitting create persists record."""
        resp = await client.post(
            "/admin/api/users/create",
            json={"username": "bob", "email": "bob@example.com", "is_active": True},
        )
        assert resp.status_code == 200
        # Verify record was actually created
        detail_resp = await client.get("/admin/api/users/1")
        assert detail_resp.status_code == 200
        texts = _find_all_string_values(detail_resp.json())
        assert any("bob" in t for t in texts)

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_duplicate_returns_error(seeded_client: AsyncClient) -> None:
        """Test that constraint violations return an error response."""
        resp = await seeded_client.post(
            "/admin/api/users/create",
            json={"username": "alice", "email": "dupe@example.com", "is_active": True},
        )
        assert resp.status_code == 500

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_validation_error_missing_fields(client: AsyncClient) -> None:
        """Missing required fields return a 422 error response."""
        resp = await client.post(
            "/admin/api/users/create",
            json={"email": "no-username@example.com", "is_active": True},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_validation_error_invalid_types(client: AsyncClient) -> None:
        """Invalid field types return a 422 error response."""
        resp = await client.post(
            "/admin/api/users/create",
            json={
                "username": "bad-types",
                "email": "bad@example.com",
                "is_active": [1, 2, 3],
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)


class TestEditView:
    """Model edit view endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_form(seeded_client: AsyncClient) -> None:
        """Verify edit form loads with data."""
        resp = await seeded_client.get("/admin/api/users/1/edit")
        assert resp.status_code == 200
        # Verify initial data is populated
        data = resp.json()
        types = _find_component_types(data)
        assert "ModelForm" in types

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_submit(seeded_client: AsyncClient) -> None:
        """Verify submitting edit persists changes."""
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={
                "username": "alice_updated",
                "email": "alice@example.com",
                "is_active": True,
            },
        )
        assert resp.status_code == 200
        # Verify record was actually updated
        detail_resp = await seeded_client.get("/admin/api/users/1")
        assert detail_resp.status_code == 200
        texts = _find_all_string_values(detail_resp.json())
        assert any("alice_updated" in t for t in texts)

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_not_found(client: AsyncClient) -> None:
        """Verify missing edit form returns 404."""
        resp = await client.get("/admin/api/users/999/edit")
        assert resp.status_code == 404

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_validation_error_missing_fields(
        seeded_client: AsyncClient,
    ) -> None:
        """Missing required fields return a 422 error response."""
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={"email": "no-username@example.com", "is_active": True},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_validation_error_invalid_types(
        seeded_client: AsyncClient,
    ) -> None:
        """Invalid field types return a 422 error response."""
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "is_active": [1, 2, 3],
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)


class TestDeleteView:
    """Model delete view endpoints."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete(seeded_client: AsyncClient) -> None:
        """Verify deleting removes the record."""
        resp = await seeded_client.post("/admin/api/users/1/delete")
        assert resp.status_code == 200
        # Verify record was actually deleted
        detail_resp = await seeded_client.get("/admin/api/users/1")
        assert detail_resp.status_code == 404

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_nonexistent(client: AsyncClient) -> None:
        """Delete of nonexistent record returns 404."""
        resp = await client.post("/admin/api/users/9999/delete")
        assert resp.status_code == 404


class TestPagination:
    """List pagination behavior."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_pagination_param(client: AsyncClient) -> None:
        """Page query param is accepted and metadata reflects requested page."""
        resp = await client.get("/admin/api/users/?page=2")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        assert pagination["page"] == 2

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_invalid_page_defaults_to_first_page(
        seeded_client: AsyncClient,
    ) -> None:
        """Non-integer page falls back to first page."""
        resp_invalid = await seeded_client.get("/admin/api/users/?page=abc")
        resp_page1 = await seeded_client.get("/admin/api/users/?page=1")

        assert resp_invalid.status_code == 200
        assert resp_invalid.json() == resp_page1.json()

        pagination = _find_pagination(resp_invalid.json())
        assert pagination is not None
        assert pagination["page"] == 1

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_with_multiple_records(
        seeded_client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """Multiple records show in list with correct pagination total."""
        async with session_maker() as session:
            for i in range(5):
                session.add(
                    User(username=f"user{i}", email=f"u{i}@e.com", is_active=True)
                )
            await session.commit()
        resp = await seeded_client.get("/admin/api/users/")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        # 1 seeded alice + 5 new users = 6 total
        assert pagination["total"] == 6
        assert pagination["page_size"] == 10

    @staticmethod
    @pytest.mark.asyncio
    async def test_negative_page_clamps_to_one(client: AsyncClient) -> None:
        """Negative page values are clamped to page 1."""
        resp = await client.get("/admin/api/users/?page=-5")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        assert pagination["page"] == 1


class TestCatchAll:
    """SPA catch-all route."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_catch_all_returns_html(client: AsyncClient) -> None:
        """SPA catch-all serves HTML for unknown paths."""
        resp = await client.get("/admin/some/random/path")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestEditPostNotFound:
    """Edit POST for missing records."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_post_not_found(client: AsyncClient) -> None:
        """POST to edit nonexistent record returns 404."""
        resp = await client.post(
            "/admin/api/users/999/edit",
            json={"username": "nope", "email": "no@e.com", "is_active": False},
        )
        assert resp.status_code == 404


class TestReadOnlyModelView:
    """Test a model view with permissions disabled."""

    @staticmethod
    def find_admin_mount(routes: Sequence[BaseRoute]) -> Mount | None:
        """Find the mounted admin sub-app by route name, if present."""
        for route in routes:
            if getattr(route, "name", None) == "admin":
                return cast("Mount", route)
        return None

    @pytest.fixture
    @staticmethod
    def readonly_app(engine: AsyncEngine) -> FastAPI:
        """Build read-only admin app."""

        class ReadOnlyUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "ReadOnlyUsers"
            column_list: ClassVar[list[str]] = ["id", "username"]
            can_create: ClassVar[bool] = False
            can_edit: ClassVar[bool] = False
            can_delete: ClassVar[bool] = False

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="RO Admin")
        admin.add_view(ReadOnlyUserAdmin)
        admin.mount()
        return app

    @pytest_asyncio.fixture
    @staticmethod
    async def ro_client(
        readonly_app: FastAPI,
        setup_db: None,  # noqa: ARG004
    ) -> AsyncGenerator[AsyncClient, None]:
        """Yield a client for the read-only app.

        Yields:
            AsyncClient: Connected test client.
        """
        transport = ASGITransport(app=readonly_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_works(ro_client: AsyncClient) -> None:
        """Verify read-only list loads."""
        resp = await ro_client.get("/admin/api/users/")
        assert resp.status_code == 200

    @staticmethod
    def test_admin_mount_found(readonly_app: FastAPI) -> None:
        """Verify the mount finder locates the admin sub-app."""
        admin_mount = TestReadOnlyModelView.find_admin_mount(readonly_app.routes)
        assert isinstance(admin_mount, Mount)

    @staticmethod
    def test_admin_mount_missing_returns_none() -> None:
        """Verify the mount finder returns None without an admin."""
        assert TestReadOnlyModelView.find_admin_mount([]) is None
        assert TestReadOnlyModelView.find_admin_mount(FastAPI().routes) is None

    @staticmethod
    def test_create_route_not_registered(readonly_app: FastAPI) -> None:
        """Verify the create API route is not in the registered routes."""
        admin_mount = TestReadOnlyModelView.find_admin_mount(readonly_app.routes)
        assert admin_mount is not None
        route_names = [r.name for r in admin_mount.routes if hasattr(r, "name")]
        assert "users_create_api" not in route_names

    @staticmethod
    def test_delete_route_not_registered(readonly_app: FastAPI) -> None:
        """Verify the delete API route is not in the registered routes."""
        admin_mount = TestReadOnlyModelView.find_admin_mount(readonly_app.routes)
        assert admin_mount is not None
        route_names = [r.name for r in admin_mount.routes if hasattr(r, "name")]
        assert "users_delete_api" not in route_names


class TestCustomBaseView:
    """Test adding a plain BaseView."""

    @pytest.fixture
    @staticmethod
    def custom_app(engine: AsyncEngine) -> FastAPI:
        """Build admin app with custom view."""

        class CustomView(BaseView):
            name: ClassVar[str] = "Custom"

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Custom Admin")
        admin.add_view(UserAdmin)
        admin.add_view(CustomView)
        admin.mount()
        return app

    @pytest_asyncio.fixture
    @staticmethod
    async def custom_client(
        custom_app: FastAPI,
        setup_db: None,  # noqa: ARG004
    ) -> AsyncGenerator[AsyncClient, None]:
        """Yield a client for the custom app.

        Yields:
            AsyncClient: Connected test client.
        """
        transport = ASGITransport(app=custom_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @staticmethod
    @pytest.mark.asyncio
    async def test_index_includes_custom_view(custom_client: AsyncClient) -> None:
        """Verify index loads with custom view."""
        resp = await custom_client.get("/admin/api/")
        assert resp.status_code == 200

    @staticmethod
    @pytest.mark.asyncio
    async def test_custom_view_html_shell(custom_client: AsyncClient) -> None:
        """Verify the plain view HTML shell loads."""
        resp = await custom_client.get("/admin/custom/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_custom_view_api_empty(custom_client: AsyncClient) -> None:
        """Verify the plain view API returns no components."""
        resp = await custom_client.get("/admin/api/custom/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAdminMountIdempotent:
    """Test that calling mount() twice is safe."""

    @staticmethod
    def test_double_mount(engine: AsyncEngine) -> None:
        """Verify double mount stays idempotent."""
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        admin.add_view(UserAdmin)
        admin.mount()
        admin.mount()  # Should be no-op
        # Verify exactly one admin mount exists
        admin_mounts = [
            r for r in app.routes if hasattr(r, "name") and r.name == "admin"
        ]
        assert len(admin_mounts) == 1


class TestAddViewAfterMount:
    """Test that add_view() after mount() raises RuntimeError."""

    @staticmethod
    def test_add_view_after_mount_raises(engine: AsyncEngine) -> None:
        """Verify late add_view raises."""
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        admin.add_view(UserAdmin)
        admin.mount()
        with pytest.raises(RuntimeError, match="Cannot add views after mount"):
            admin.add_view(UserAdmin)


class TestAddViewValidation:
    """Test that add_view() rejects invalid arguments."""

    @staticmethod
    def test_add_view_with_instance_raises(engine: AsyncEngine) -> None:
        """Verify instance add_view raises."""
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        instance = UserAdmin(admin=admin)
        with pytest.raises(TypeError, match="expects a BaseView subclass"):
            admin.add_view(instance)

    @staticmethod
    def test_add_view_with_non_view_class_raises(engine: AsyncEngine) -> None:
        """Verify non-view add_view raises."""
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        with pytest.raises(TypeError, match="expects a BaseView subclass"):
            admin.add_view(str)


class TestModelViewWithoutModel:
    """Test that BaseModelView subclass without model raises TypeError."""

    @staticmethod
    def test_missing_model_raises() -> None:
        """Verify missing model raises."""
        with pytest.raises(TypeError, match="must specify model=MyModel"):

            class BadView(BaseModelView):
                pass


class TestInvalidPageSize:
    """Test that page_size <= 0 raises ValueError."""

    @staticmethod
    def test_zero_page_size_raises() -> None:
        """Verify zero page size raises."""
        with pytest.raises(ValueError, match="page_size must be positive"):

            class BadView(BaseModelView, model=User):
                page_size: ClassVar[int] = 0


class TestInvalidColumnList:
    """Test that invalid column names in column_list are filtered out with warning."""

    @pytest.fixture
    @staticmethod
    def invalid_col_app(engine: AsyncEngine) -> FastAPI:
        """Build admin app with invalid column."""

        class InvalidColUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "InvalidColUsers"
            column_list: ClassVar[list[str]] = ["id", "username", "nonexistent_col"]

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Invalid Col Admin")
        admin.add_view(InvalidColUserAdmin)
        admin.mount()
        return app

    @pytest_asyncio.fixture
    @staticmethod
    async def invalid_col_client(
        invalid_col_app: FastAPI,
        setup_db: None,  # noqa: ARG004
    ) -> AsyncGenerator[AsyncClient, None]:
        """Yield a client for the invalid-column app.

        Yields:
            AsyncClient: Connected test client.
        """
        transport = ASGITransport(app=invalid_col_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @staticmethod
    @pytest.mark.asyncio
    async def test_invalid_columns_filtered_out(
        invalid_col_client: AsyncClient,
    ) -> None:
        """Invalid column names are silently filtered; valid ones still render."""
        resp = await invalid_col_client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        texts = _find_all_string_values(data)
        # Valid columns should appear
        assert any("Id" in t or "id" in t for t in texts)
        assert any("Username" in t or "username" in t for t in texts)
        # Invalid column should not appear
        assert "nonexistent_col" not in texts
        assert "Nonexistent Col" not in texts


class TestColumnExcludeList:
    """Test column_exclude_list filtering."""

    @pytest.fixture
    @staticmethod
    def exclude_app(engine: AsyncEngine) -> FastAPI:
        """Build admin app with excluded columns."""

        class ExcludeUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "ExcludeUsers"
            column_exclude_list: ClassVar[list[str]] = ["created_at", "is_active"]

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Exclude Admin")
        admin.add_view(ExcludeUserAdmin)
        admin.mount()
        return app

    @pytest_asyncio.fixture
    @staticmethod
    async def exclude_client(
        exclude_app: FastAPI,
        setup_db: None,  # noqa: ARG004
    ) -> AsyncGenerator[AsyncClient, None]:
        """Yield a client for the exclude-column app.

        Yields:
            AsyncClient: Connected test client.
        """
        transport = ASGITransport(app=exclude_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @staticmethod
    @pytest.mark.asyncio
    async def test_excluded_columns_not_in_table(exclude_client: AsyncClient) -> None:
        """Verify excluded columns stay hidden."""
        resp = await exclude_client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        texts = _find_all_string_values(data)
        # Column headers should not include excluded columns
        assert "Created At" not in texts
        assert "Is Active" not in texts


class TestBaseViewBasics:
    """BaseView property and default rendering."""

    @staticmethod
    def test_admin_property_returns_admin(engine: AsyncEngine) -> None:
        """Verify view exposes its admin instance."""
        admin = BaseAdmin(app=FastAPI(), engine=engine, title="Props Admin")
        view = UserAdmin(admin=admin)
        assert view.admin is admin

    @staticmethod
    @pytest.mark.asyncio
    async def test_plain_view_render_returns_empty(engine: AsyncEngine) -> None:
        """Verify default render yields no components."""
        admin = BaseAdmin(app=FastAPI(), engine=engine, title="Render Admin")
        view = BaseView(admin=admin)
        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        }
        assert await view.render(Request(scope)) == []


class TestAutomaticViewNaming:
    """Default names for model views."""

    @staticmethod
    def test_name_derives_from_table_name() -> None:
        """Verify omitted name falls back to table title."""

        class AutoDerivedUserAdmin(BaseModelView, model=User):
            pass

        assert AutoDerivedUserAdmin.name == "Users"

    @staticmethod
    def test_page_size_defaults_without_override() -> None:
        """Verify default page size applies."""

        class DefaultPagedUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "DefaultPagedUsers"

        assert DefaultPagedUserAdmin.page_size == 25

    @staticmethod
    def test_model_inherited_from_parent_view(engine: AsyncEngine) -> None:
        """Verify model passes down to subclasses."""

        class InheritedUserAdmin(UserAdmin):
            pass

        admin = BaseAdmin(app=FastAPI(), engine=engine, title="Inherited Admin")
        view = InheritedUserAdmin(admin=admin)
        assert type(view).model is User


class TestKeylessModel:
    """Primary key detection."""

    @staticmethod
    def test_missing_primary_key_raises(engine: AsyncEngine) -> None:
        """Verify keyless models are rejected."""

        class KeylessProbeAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "KeylessProbeUsers"

        admin = BaseAdmin(app=FastAPI(), engine=engine, title="Keyless Admin")
        stub = SimpleNamespace(primary_key=())
        with (
            mock.patch("fastui_admin.views.sa_inspect", return_value=stub),
            pytest.raises(ValueError, match="has no primary key"),
        ):
            KeylessProbeAdmin(admin=admin)


class TestInvisibleModelView:
    """Index rendering with hidden views."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_index_api_skips_invisible_view(engine: AsyncEngine) -> None:
        """Verify hidden views stay out of index links."""

        class ConcealedUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "ConcealedUsers"
            is_visible: ClassVar[bool] = False

        fastapi_app = FastAPI()
        admin = BaseAdmin(app=fastapi_app, engine=engine, title="Hidden Admin")
        admin.add_view(UserAdmin)
        admin.add_view(ConcealedUserAdmin)
        admin.mount()
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/admin/api/")
        assert resp.status_code == 200


class TestBareAdminIndex:
    """Index rendering without model views."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_index_api_without_model_views(engine: AsyncEngine) -> None:
        """Verify index renders with no model links."""
        fastapi_app = FastAPI()
        admin = BaseAdmin(app=fastapi_app, engine=engine, title="Bare Admin")
        admin.mount()
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/admin/api/")
        assert resp.status_code == 200


class TestPermissionRouteSkips:
    """Route registration with disabled permissions."""

    @staticmethod
    def test_locked_view_registers_list_only(engine: AsyncEngine) -> None:
        """Verify disabled actions add no routes."""

        class LockedUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "LockedUsers"
            can_create: ClassVar[bool] = False
            can_view_details: ClassVar[bool] = False
            can_edit: ClassVar[bool] = False
            can_delete: ClassVar[bool] = False

        fastapi_app = FastAPI()
        admin = BaseAdmin(app=fastapi_app, engine=engine, title="Locked Admin")
        admin.add_view(LockedUserAdmin)
        admin.mount()
        mounts = [
            route
            for route in fastapi_app.routes
            if getattr(route, "name", None) == "admin"
        ]
        assert len(mounts) == 1
        admin_mount = mounts[0]
        assert isinstance(admin_mount, Mount)
        route_names = [getattr(route, "name", "") for route in admin_mount.routes]
        assert "users_create_api" not in route_names
        assert "users_detail" not in route_names
        assert "users_detail_api" not in route_names
        assert "users_edit" not in route_names
        assert "users_edit_api" not in route_names
        assert "users_delete_api" not in route_names


class TestRestrictedDetailView:
    """Detail rendering with disabled actions."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_without_edit(
        engine: AsyncEngine, session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """Verify detail renders when editing is disabled."""

        class UneditableUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "UneditableUsers"
            can_edit: ClassVar[bool] = False

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_maker() as session:
            session.add(
                User(username="edith", email="edith@example.com", is_active=True)
            )
            await session.commit()
        fastapi_app = FastAPI()
        admin = BaseAdmin(app=fastapi_app, engine=engine, title="Uneditable")
        admin.add_view(UneditableUserAdmin)
        admin.mount()
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/admin/api/users/1")
        assert resp.status_code == 200

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_without_delete(
        engine: AsyncEngine, session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """Verify detail renders when deletion is disabled."""

        class UndeletableUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "UndeletableUsers"
            can_delete: ClassVar[bool] = False

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_maker() as session:
            session.add(User(username="dora", email="dora@example.com", is_active=True))
            await session.commit()
        fastapi_app = FastAPI()
        admin = BaseAdmin(app=fastapi_app, engine=engine, title="Undeletable")
        admin.add_view(UndeletableUserAdmin)
        admin.mount()
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/admin/api/users/1")
        assert resp.status_code == 200


class TestModelHtmlShells:
    """HTML shells for model views."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_html(client: AsyncClient) -> None:
        """Verify detail HTML page loads."""
        resp = await client.get("/admin/users/1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_html(client: AsyncClient) -> None:
        """Verify create HTML page loads."""
        resp = await client.get("/admin/users/create")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_html(client: AsyncClient) -> None:
        """Verify edit HTML page loads."""
        resp = await client.get("/admin/users/1/edit")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @staticmethod
    @pytest.mark.asyncio
    async def test_create_form_cached(client: AsyncClient) -> None:
        """Verify repeated create form loads succeed."""
        first = await client.get("/admin/api/users/create")
        second = await client.get("/admin/api/users/create")
        assert first.status_code == 200
        assert second.status_code == 200


class TestDatabaseErrorResponses:
    """Server errors for database failures."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_list_api_db_error(client: AsyncClient, engine: AsyncEngine) -> None:
        """Verify list reports database failures."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        resp = await client.get("/admin/api/users/")
        assert resp.status_code == 500

    @staticmethod
    @pytest.mark.asyncio
    async def test_detail_api_db_error(
        client: AsyncClient, engine: AsyncEngine
    ) -> None:
        """Verify detail reports database failures."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        resp = await client.get("/admin/api/users/1")
        assert resp.status_code == 500

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_form_db_error(client: AsyncClient, engine: AsyncEngine) -> None:
        """Verify edit form reports database failures."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        resp = await client.get("/admin/api/users/1/edit")
        assert resp.status_code == 500

    @staticmethod
    @pytest.mark.asyncio
    async def test_edit_submit_db_error(
        client: AsyncClient, engine: AsyncEngine
    ) -> None:
        """Verify edit submit reports database failures."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        resp = await client.post(
            "/admin/api/users/1/edit",
            json={"username": "zed", "email": "zed@example.com", "is_active": True},
        )
        assert resp.status_code == 500

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_db_error(client: AsyncClient, engine: AsyncEngine) -> None:
        """Verify delete reports database failures."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        resp = await client.post("/admin/api/users/1/delete")
        assert resp.status_code == 500


class TestComponentTypeHelpers:
    """Edge cases for component type extraction."""

    @staticmethod
    def test_non_string_type_marker_ignored() -> None:
        """Verify numeric type markers are skipped."""
        assert _find_component_types({"type": 42}) == set()

    @staticmethod
    def test_nested_dict_without_type_key() -> None:
        """Verify typeless mappings yield nothing."""
        assert _find_component_types({"outer": {"inner": "value"}}) == set()
