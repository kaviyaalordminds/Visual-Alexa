from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import PluginState

from app.db.base import Base, IDMixin, TimestampMixin


class Plugin(Base, IDMixin, TimestampMixin):
    """docs/phase-7/PLUGIN-ARCHITECTURE.md — a plugin never starts
    trusted. `manifest` is the full `PluginManifest` dump (what was
    installed, for audit/re-review), never mutated after install; the
    live, currently-granted permission set lives in `PluginPermission`
    rows instead."""

    __tablename__ = "plugins"

    manifest_id: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    author: Mapped[str] = mapped_column(String(200))
    state: Mapped[PluginState] = mapped_column(Enum(PluginState), default=PluginState.UNTRUSTED)
    manifest: Mapped[dict] = mapped_column(JSON)


class PluginPermission(Base, IDMixin, TimestampMixin):
    """One row per permission a plugin's manifest *requested* —
    `granted` starts `False` for every one of them (brief §65: 'Default:
    DENY'), regardless of `Plugin.state`."""

    __tablename__ = "plugin_permissions"

    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.id"))
    permission: Mapped[str] = mapped_column(String(200))
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
