"""Plugin manifest contract. docs/phase-7/PLUGIN-ARCHITECTURE.md §62.

`permissions` is a flat list of scope strings, deliberately not a typed
enum — the same convention `ToolDefinition.required_permission` already
uses (an opaque string the Policy Engine/PluginRegistry evaluates), kept
consistent rather than introducing a second, parallel permission-typing
scheme.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str
    permissions: list[str] = Field(default_factory=list)
    tools: list[str] = Field(
        default_factory=list, description="Tool ids this plugin registers once ENABLED."
    )
    dependencies: list[str] = Field(default_factory=list)
    entrypoint: str
    platforms: list[str] = Field(default_factory=list)
