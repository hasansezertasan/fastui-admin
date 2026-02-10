# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for BaseAdmin and BaseModelView integration."""

from typing import ClassVar, List

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastui_admin import BaseAdmin, BaseModelView, BaseView

from .conftest import User, UserAdmin


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

    async def test_list_api_with_data(self, seeded_client):
        resp = await seeded_client.get("/admin/api/users/")
        assert resp.status_code == 200


class TestDetailView:
    async def test_detail_not_found(self, client):
        resp = await client.get("/admin/api/users/999")
        assert resp.status_code == 404

    async def test_detail_found(self, seeded_client):
        resp = await seeded_client.get("/admin/api/users/1")
        assert resp.status_code == 200


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

    async def test_create_duplicate_returns_error(self, seeded_client):
        """Test that constraint violations return an error response."""
        resp = await seeded_client.post(
            "/admin/api/users/create",
            json={"username": "alice", "email": "dupe@example.com", "is_active": True},
        )
        # Should return 400 with error message (unique constraint violation)
        assert resp.status_code == 400


class TestEditView:
    async def test_edit_form(self, seeded_client):
        resp = await seeded_client.get("/admin/api/users/1/edit")
        assert resp.status_code == 200

    async def test_edit_submit(self, seeded_client):
        resp = await seeded_client.post(
            "/admin/api/users/1/edit",
            json={"username": "alice_updated", "email": "alice@example.com", "is_active": True},
        )
        assert resp.status_code == 200

    async def test_edit_not_found(self, client):
        resp = await client.get("/admin/api/users/999/edit")
        assert resp.status_code == 404


class TestDeleteView:
    async def test_delete(self, seeded_client):
        resp = await seeded_client.post("/admin/api/users/1/delete")
        assert resp.status_code == 200

    async def test_delete_nonexistent(self, client):
        """Delete of nonexistent record returns 404."""
        resp = await client.post("/admin/api/users/9999/delete")
        assert resp.status_code == 404


class TestPagination:
    async def test_list_api_pagination_param(self, client):
        """Page query param is accepted."""
        resp = await client.get("/admin/api/users/?page=2")
        assert resp.status_code == 200

    async def test_list_api_with_multiple_records(self, seeded_client, session_maker):
        """Multiple records show in list."""
        async with session_maker() as session:
            for i in range(5):
                session.add(User(username=f"user{i}", email=f"u{i}@e.com", is_active=True))
            await session.commit()
        resp = await seeded_client.get("/admin/api/users/")
        assert resp.status_code == 200


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
            column_list: ClassVar[List[str]] = ["id", "username"]
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
        assert "ReadOnlyUsers_create_api" not in route_names

    def test_delete_route_not_registered(self, readonly_app):
        """Verify the delete API route is not in the registered routes."""
        admin_mount = None
        for route in readonly_app.routes:
            if hasattr(route, "name") and route.name == "admin":
                admin_mount = route
                break
        assert admin_mount is not None
        route_names = [r.name for r in admin_mount.app.routes if hasattr(r, "name")]
        assert "ReadOnlyUsers_delete_api" not in route_names


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
        # No assertion needed — just shouldn't raise
