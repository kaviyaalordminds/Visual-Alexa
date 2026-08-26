"""Loads the DB-backed Application Registry into an in-memory
`computer_control.registry.ApplicationRegistry` at process startup —
mirrors the `tool_registry` bootstrap pattern in
app/services/bootstrap.py. docs/phase-2/APPLICATION-CONTROL.md.
"""

from __future__ import annotations

from computer_control.registry import ApplicationRegistry, ApplicationRegistryEntry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application as ApplicationRow

application_registry = ApplicationRegistry([])


def _row_to_entry(row: ApplicationRow) -> ApplicationRegistryEntry:
    return ApplicationRegistryEntry(
        identifier=row.identifier,
        name=row.name,
        aliases=tuple(row.aliases),
        executable_candidates=tuple(row.executable_candidates),
        publisher=row.publisher,
        risk_level=row.risk_level,
        enabled=row.enabled,
        verification_strategy=row.verification_strategy,
    )


async def load_application_registry(session: AsyncSession) -> ApplicationRegistry:
    result = await session.execute(select(ApplicationRow))
    entries = [_row_to_entry(row) for row in result.scalars()]
    global application_registry
    application_registry = ApplicationRegistry(entries)
    return application_registry
