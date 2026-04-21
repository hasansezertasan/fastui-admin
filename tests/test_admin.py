# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for BaseAdmin and BaseModelView integration."""

from typing import Any, ClassVar

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastui_admin import BaseAdmin, BaseModelView, BaseView

from .conftest import User, UserAdmin


def _find_component_types(data: Any) -> set[str]:
    """Recursively extract all component 'type' values from a FastUI JSON response."""
    types: set[str] = set()
    if isinstance(data, dict):
        if "type" in data:
            types.add(data["type"])
        for v in data.values():
            types.update(_find_component_types(v))
    elif isinstance(data, list):
        for item in data:
            types.update(_find_component_types(item))
    return types


def _find_pagination(data: Any) -> Any:
    """Recursively find the Pagination component dict in a FastUI JSON response."""
    if isinstance(data, dict):
        if data.get("type") == "Pagination":
            return data
        for v in data.values():
            result = _find_pagination(v)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_pagination(item)
            if result is not None:
                return result
    return None


def _find_all_string_values(data: Any) -> list[str]:
    """Recursively extract all string values from a JSON structure."""
    values: list[str] = []
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, str):
                values.append(v)
            else:
                values.extend(_find_all_string_values(v))
    elif isinstance(data, list):
        for item in data:
            values.extend(_find_all_string_values(item))
    return values


@pytest_asyncio.fixture()
async def client(app, setup_db):  # noqa: ARG001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def seeded_client(client, session_maker):
    """Client with a user already in the database."""
    async with session_maker() as session:
        user = User(username="alice", email="alice@example.com", is_active=True)
        session.add(user)
        await session.commit()
    return client


class TestAdminIndex:
    async def test_index_html(self, client):
        resp = await client.get("/admin/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_index_api(self, client):
        resp = await client.get("/admin/api/")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"


class TestListView:
    async def test_list_html(self, client):
        resp = await client.get("/admin/users/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    async def test_list_api_empty(self, client):
        resp = await client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        types = _find_component_types(data)
        assert "Table" in types
        assert "Pagination" in types

    async def test_list_api_with_data(self, seeded_client):
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
        assert any("alice" in t for t in texts), "Seeded user 'alice' should appear in table"


class TestDetailView:
    async def test_detail_not_found(self, client):
        resp = await client.get("/admin/api/users/999")
        assert resp.status_code == 404
        # Should return FastUI components, not raw JSON
        data = resp.json()
        assert isinstance(data, list)

    async def test_detail_found(self, seeded_client):
        resp = await seeded_client.get("/admin/api/users/1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        types = _find_component_types(data)
        assert "Details" in types
        assert "Heading" in types


class TestCreateView:
    async def test_create_form(self, client):
        resp = await client.get("/admin/api/users/create")
        assert resp.status_code == 200

    async def test_create_submit(self, client):
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

    async def test_create_duplicate_returns_error(self, seeded_client):
        """Test that constraint violations return an error response."""
        resp = await seeded_client.post(
            "/admin/api/users/create",
            json={"username": "alice", "email": "dupe@example.com", "is_active": True},
        )
        assert resp.status_code == 500

    async def test_create_validation_error_missing_fields(self, client):
        """Missing required fields return a 422 error response."""
        resp = await client.post(
            "/admin/api/users/create",
            json={"email": "no-username@example.com", "is_active": True},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)

    async def test_create_validation_error_invalid_types(self, client):
        """Invalid field types return a 422 error response."""
        resp = await client.post(
            "/admin/api/users/create",
            json={"username": "bad-types", "email": "bad@example.com", "is_active": "not-a-bool"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)


class TestEditView:
    async def test_edit_form(self, seeded_client):
        resp = await seeded_client.get("/admin/api/users/1/edit")
        assert resp.status_code == 200
        # Verify initial data is populated
        data = resp.json()
        types = _find_component_types(data)
        assert "ModelForm" in types

    async def test_edit_submit(self, seeded_client):
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={"username": "alice_updated", "email": "alice@example.com", "is_active": True},
        )
        assert resp.status_code == 200
        # Verify record was actually updated
        detail_resp = await seeded_client.get("/admin/api/users/1")
        assert detail_resp.status_code == 200
        texts = _find_all_string_values(detail_resp.json())
        assert any("alice_updated" in t for t in texts)

    async def test_edit_not_found(self, client):
        resp = await client.get("/admin/api/users/999/edit")
        assert resp.status_code == 404

    async def test_edit_validation_error_missing_fields(self, seeded_client):
        """Missing required fields return a 422 error response."""
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={"email": "no-username@example.com", "is_active": True},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)

    async def test_edit_validation_error_invalid_types(self, seeded_client):
        """Invalid field types return a 422 error response."""
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={"username": "alice", "email": "alice@example.com", "is_active": "not-a-bool"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data, list)


class TestDeleteView:
    async def test_delete(self, seeded_client):
        resp = await seeded_client.post("/admin/api/users/1/delete")
        assert resp.status_code == 200
        # Verify record was actually deleted
        detail_resp = await seeded_client.get("/admin/api/users/1")
        assert detail_resp.status_code == 404

    async def test_delete_nonexistent(self, client):
        """Delete of nonexistent record returns 404."""
        resp = await client.post("/admin/api/users/9999/delete")
        assert resp.status_code == 404


class TestPagination:
    async def test_list_api_pagination_param(self, client):
        """Page query param is accepted and metadata reflects requested page."""
        resp = await client.get("/admin/api/users/?page=2")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        assert pagination["page"] == 2

    async def test_list_api_invalid_page_defaults_to_first_page(self, seeded_client):
        """Non-integer page falls back to first page."""
        resp_invalid = await seeded_client.get("/admin/api/users/?page=abc")
        resp_page1 = await seeded_client.get("/admin/api/users/?page=1")

        assert resp_invalid.status_code == 200
        assert resp_invalid.json() == resp_page1.json()

        pagination = _find_pagination(resp_invalid.json())
        assert pagination is not None
        assert pagination["page"] == 1

    async def test_list_api_with_multiple_records(self, seeded_client, session_maker):
        """Multiple records show in list with correct pagination total."""
        async with session_maker() as session:
            for i in range(5):
                session.add(User(username=f"user{i}", email=f"u{i}@e.com", is_active=True))
            await session.commit()
        resp = await seeded_client.get("/admin/api/users/")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        # 1 seeded alice + 5 new users = 6 total
        assert pagination["total"] == 6
        assert pagination["page_size"] == 10

    async def test_negative_page_clamps_to_one(self, client):
        """Negative page values are clamped to page 1."""
        resp = await client.get("/admin/api/users/?page=-5")
        assert resp.status_code == 200
        pagination = _find_pagination(resp.json())
        assert pagination is not None
        assert pagination["page"] == 1


class TestCatchAll:
    async def test_catch_all_returns_html(self, client):
        """SPA catch-all serves HTML for unknown paths."""
        resp = await client.get("/admin/some/random/path")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestEditPostNotFound:
    async def test_edit_post_not_found(self, client):
        """POST to edit nonexistent record returns 404."""
        resp = await client.post(
            "/admin/api/users/999/edit",
            json={"username": "nope", "email": "no@e.com", "is_active": False},
        )
        assert resp.status_code == 404


class TestReadOnlyModelView:
    """Test a model view with permissions disabled."""

    @pytest.fixture()
    def readonly_app(self, engine):
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

    @pytest_asyncio.fixture()
    async def ro_client(self, readonly_app, setup_db):  # noqa: ARG002
        transport = ASGITransport(app=readonly_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_list_works(self, ro_client):
        resp = await ro_client.get("/admin/api/users/")
        assert resp.status_code == 200

    def test_create_route_not_registered(self, readonly_app):
        """Verify the create API route is not in the registered routes."""
        admin_mount = None
        for route in readonly_app.routes:
            if hasattr(route, "name") and route.name == "admin":
                admin_mount = route
                break
        assert admin_mount is not None
        route_names = [r.name for r in admin_mount.app.routes if hasattr(r, "name")]
        assert "users_create_api" not in route_names

    def test_delete_route_not_registered(self, readonly_app):
        """Verify the delete API route is not in the registered routes."""
        admin_mount = None
        for route in readonly_app.routes:
            if hasattr(route, "name") and route.name == "admin":
                admin_mount = route
                break
        assert admin_mount is not None
        route_names = [r.name for r in admin_mount.app.routes if hasattr(r, "name")]
        assert "users_delete_api" not in route_names


class TestCustomBaseView:
    """Test adding a plain BaseView."""

    @pytest.fixture()
    def custom_app(self, engine):
        class CustomView(BaseView):
            name: ClassVar[str] = "Custom"

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Custom Admin")
        admin.add_view(UserAdmin)
        admin.add_view(CustomView)
        admin.mount()
        return app

    @pytest_asyncio.fixture()
    async def custom_client(self, custom_app, setup_db):  # noqa: ARG002
        transport = ASGITransport(app=custom_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_index_includes_custom_view(self, custom_client):
        resp = await custom_client.get("/admin/api/")
        assert resp.status_code == 200


class TestAdminMountIdempotent:
    """Test that calling mount() twice is safe."""

    def test_double_mount(self, engine):
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        admin.add_view(UserAdmin)
        admin.mount()
        admin.mount()  # Should be no-op
        # Verify exactly one admin mount exists
        admin_mounts = [r for r in app.routes if hasattr(r, "name") and r.name == "admin"]
        assert len(admin_mounts) == 1


class TestAddViewAfterMount:
    """Test that add_view() after mount() raises RuntimeError."""

    def test_add_view_after_mount_raises(self, engine):
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        admin.add_view(UserAdmin)
        admin.mount()
        with pytest.raises(RuntimeError, match="Cannot add views after mount"):
            admin.add_view(UserAdmin)


class TestAddViewValidation:
    """Test that add_view() rejects invalid arguments."""

    def test_add_view_with_instance_raises(self, engine):
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        instance = UserAdmin(admin=admin)
        with pytest.raises(TypeError, match="expects a BaseView subclass"):
            admin.add_view(instance)  # type: ignore[arg-type]

    def test_add_view_with_non_view_class_raises(self, engine):
        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Test")
        with pytest.raises(TypeError, match="expects a BaseView subclass"):
            admin.add_view(str)  # type: ignore[arg-type]


class TestModelViewWithoutModel:
    """Test that BaseModelView subclass without model raises TypeError."""

    def test_missing_model_raises(self):
        with pytest.raises(TypeError, match="must specify model=MyModel"):

            class BadView(BaseModelView):
                pass


class TestInvalidPageSize:
    """Test that page_size <= 0 raises ValueError."""

    def test_zero_page_size_raises(self):
        with pytest.raises(ValueError, match="page_size must be positive"):

            class BadView(BaseModelView, model=User):
                page_size: ClassVar[int] = 0


class TestInvalidColumnList:
    """Test that invalid column names in column_list are filtered out with warning."""

    @pytest.fixture()
    def invalid_col_app(self, engine):
        class InvalidColUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "InvalidColUsers"
            column_list: ClassVar[list[str]] = ["id", "username", "nonexistent_col"]

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Invalid Col Admin")
        admin.add_view(InvalidColUserAdmin)
        admin.mount()
        return app

    @pytest_asyncio.fixture()
    async def invalid_col_client(self, invalid_col_app, setup_db):  # noqa: ARG002
        transport = ASGITransport(app=invalid_col_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_invalid_columns_filtered_out(self, invalid_col_client):
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

    @pytest.fixture()
    def exclude_app(self, engine):
        class ExcludeUserAdmin(BaseModelView, model=User):
            name: ClassVar[str] = "ExcludeUsers"
            column_exclude_list: ClassVar[list[str]] = ["created_at", "is_active"]

        app = FastAPI()
        admin = BaseAdmin(app=app, engine=engine, title="Exclude Admin")
        admin.add_view(ExcludeUserAdmin)
        admin.mount()
        return app

    @pytest_asyncio.fixture()
    async def exclude_client(self, exclude_app, setup_db):  # noqa: ARG002
        transport = ASGITransport(app=exclude_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_excluded_columns_not_in_table(self, exclude_client):
        resp = await exclude_client.get("/admin/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        texts = _find_all_string_values(data)
        # Column headers should not include excluded columns
        assert "Created At" not in texts
        assert "Is Active" not in texts
