# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""
Read-only admin example — demonstrates permission flags.

Run with:
    uvicorn examples.readonly.main:app --reload --port 5000

Then visit:
    http://localhost:5000/admin/
"""

from datetime import datetime, timezone
from typing import ClassVar, List

from fastapi import FastAPI
from sqlalchemy import DateTime, Float, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastui_admin import BaseAdmin, BaseModelView

# --- Model ---


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    """Immutable audit log — read-only in the admin."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(50))
    user: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(500))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Product(Base):
    """Products can be viewed and edited but not deleted."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float)
    sku: Mapped[str] = mapped_column(String(50), unique=True)


# --- Admin Views ---


class AuditLogAdmin(BaseModelView, model=AuditLog):
    name: ClassVar[str] = "Audit Logs"
    column_list: ClassVar[List[str]] = ["id", "action", "user", "detail", "timestamp"]
    can_create: ClassVar[bool] = False
    can_edit: ClassVar[bool] = False
    can_delete: ClassVar[bool] = False


class ProductAdmin(BaseModelView, model=Product):
    name: ClassVar[str] = "Products"
    column_list: ClassVar[List[str]] = ["id", "name", "price", "sku"]
    can_delete: ClassVar[bool] = False


# --- App ---

engine = create_async_engine("sqlite+aiosqlite:///./example.db", echo=True)
app = FastAPI(title="Read-Only Admin Example")


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


admin = BaseAdmin(app=app, engine=engine, title="Read-Only Admin")
admin.add_view(AuditLogAdmin)
admin.add_view(ProductAdmin)
admin.mount()


@app.post("/seed")
async def seed_data() -> dict:
    """Seed sample data."""
    session_maker = async_sessionmaker(engine, class_=AsyncSession)
    async with session_maker() as session:
        result = await session.execute(select(AuditLog))
        if result.first():
            return {"message": "Data already exists"}

        session.add_all(
            [
                AuditLog(action="login", user="alice", detail="Logged in from 192.168.1.1"),
                AuditLog(action="create", user="alice", detail="Created product SKU-001"),
                AuditLog(action="login", user="bob", detail="Logged in from 10.0.0.5"),
                Product(name="Widget", price=9.99, sku="SKU-001"),
                Product(name="Gadget", price=24.99, sku="SKU-002"),
                Product(name="Doohickey", price=4.50, sku="SKU-003"),
            ]
        )
        await session.commit()

    return {"message": "Seed data created"}
