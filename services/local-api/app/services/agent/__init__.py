"""Phase 4 — the AI Brain: intent understanding, planning, closed-loop
execution, recovery, and confirmation, orchestrated by `AgentOrchestrator`.

Lives in `services/local-api` rather than a new top-level package —
CLAUDE.md: 'the Local API is the only process with database access and
the only process that can invoke a tool,' and this subsystem needs
direct, transactional access to `Task`/`TaskStep` rows. See
docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §2.
"""

from __future__ import annotations
