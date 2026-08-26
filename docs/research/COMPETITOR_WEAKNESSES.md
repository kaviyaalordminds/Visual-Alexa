# Competitor Weaknesses (Summary)

Entry point requested by the Phase 1 brief §4. Full, evidence-tagged detail
(30 weaknesses, each marked CONFIRMED LIMITATION / DESIGN INFERENCE / OPEN
QUESTION) lives in `03-COMPETITOR-WEAKNESSES.md`. Related: `04-TECHNICAL-LIMITATIONS.md`
(organized by subsystem), `05-UX-LIMITATIONS.md`, `06-SECURITY-RISKS.md`.

## Highest-confidence weaknesses (self-documented by frontier labs)

1. **Coordinate-based automation is fragile** — Anthropic's own computer-use
   docs note accuracy/latency trade-offs of pixel-coordinate action.
2. **Consequential actions were historically under-confirmed** — both
   Anthropic and OpenAI retrofitted confirmation/"watch mode" mitigations
   after initial release, which is itself evidence the original default was
   judged insufficient.
3. **Agent permissions are scoped by isolating the machine (a throwaway VM),
   not by scoping the agent's own capabilities** — Anthropic's documented
   mitigation is environment isolation, not fine-grained permissions.
4. **Cloud dependency is universal** — every surveyed conversational
   assistant requires a cloud round-trip for core reasoning.
5. **Prompt injection from on-screen/page content is an acknowledged, open
   risk** — both frontier labs warn about it explicitly in their own
   documentation.

See `03-COMPETITOR-WEAKNESSES.md` for the full list with per-item evidence
tags, and `07-VEYRA-DIFFERENTIATORS.md` for how each maps to a specific
architectural response.
