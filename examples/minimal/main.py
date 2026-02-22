# SPDX-FileCopyrightText: 2024-present Hasan Sezer Tasan <hasansezertasan@gmail.com>
#
# SPDX-License-Identifier: MIT
"""
Minimal FastUI Admin example — single model, fewest lines possible.

Run with:
    uvicorn examples.minimal.main:app --reload --port 5000

Then visit:
    http://localhost:5000/admin/
"""

from typing import ClassVar, List

from fastapi import FastAPI
from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastui_admin import BaseAdmin, BaseModelView

# --- Model ---


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending")


# --- App ---

engine = create_async_engine("sqlite+aiosqlite:///./example.db", echo=True)
app = FastAPI()


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class TodoAdmin(BaseModelView, model=Todo):
    name: ClassVar[str] = "Todos"
    column_list: ClassVar[List[str]] = ["id", "title", "status"]


admin = BaseAdmin(app=app, engine=engine, title="Minimal Admin")
admin.add_view(TodoAdmin)
admin.mount()
