"""Memory contracts. docs/architecture/09-MEMORY.md"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from veyra_contracts.enums import MemoryCategory


class MemoryRecord(BaseModel):
    """Every field here exists so memory stays inspectable/editable/
    deletable/auditable per docs/architecture/09-MEMORY.md §2 — no hidden
    memory."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    category: MemoryCategory
    key: str | None = Field(
        default=None, description="Alias lookup key, e.g. 'office folder'."
    )
    content: dict[str, Any]
    source: str = Field(
        description="conversation_id / task_id / 'user_explicit' — where "
        "this memory came from, for auditability."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
