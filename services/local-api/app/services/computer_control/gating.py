"""The umbrella `computer_control.enabled` gate. docs/security/05-DATA-PROTECTION.md
§3, CLAUDE.md: 'Microphone, screen capture, external devices, and remote
access are OFF by default and require explicit, visible enablement — no
exceptions.' Phase 1 seeded `computer_control.enabled = False` and the
Phase 1 status screen already showed 'Computer Control: NOT ENABLED' —
this is Phase 2 completing that promise: every computer-control tool
checks this setting, not just the ones added later.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.setting import SystemSetting

_SETTING_KEY = "computer_control.enabled"


async def computer_control_enabled() -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == _SETTING_KEY)
        )
        row = result.scalars().first()
        return bool(row.value) if row is not None else False
