"""Event contracts. docs/architecture/12-EVENTS.md"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from veyra_contracts.enums import EventType


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
