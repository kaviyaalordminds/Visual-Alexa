# VEYRA Differentiation (Summary)

Entry point requested by the Phase 1 brief §5. Full detail (17 differentiators,
each with problem / existing approach / VEYRA approach / technical design /
measurement / what Phase 1 actually delivers) lives in
`07-VEYRA-DIFFERENTIATORS.md`.

## What VEYRA is

**A local-first visual AI computer operating layer** — not merely a voice
assistant, not merely a chatbot, not merely a screen-reading AI, not merely a
computer-use agent, not merely a smart-home assistant. VEYRA's target
combines voice + vision + reasoning + computer control + memory + security +
verification + recovery + visual identity + optional authorized IoT, on the
user's own installed Windows PC as the primary environment.

## What VEYRA is not

- Not an Alexa/Siri/Copilot/Gemini clone — no shared visual identity, no
  shared wake word, no shared branding.
- Not a thin wrapper around a single computer-use model — the LLM never
  receives unrestricted OS access; every action is a typed, policy-checked
  tool call (`docs/security/01-SECURITY-ARCHITECTURE.md`).
- Not a cloud-dependent-by-default product — local-first is the default
  posture, cloud is opt-in (`docs/architecture/03-AI-ARCHITECTURE.md`).

## The four highest-confidence differentiators

Ranked by strength of external evidence for the gap they close (see
`07-VEYRA-DIFFERENTIATORS.md` items 1, 2, 3, 6 for full detail):

1. Structured, typed tool execution — the model can request, never directly
   perform, an action.
2. Capability-based permissions scoped to the tool call, not the machine.
3. Local-first execution as the architectural default, not an add-on mode.
4. An explicit Observe → Plan → Policy Check → Act → Observe → Verify →
   Recover task lifecycle, visible to the user via avatar/UI state.

Phase 1 delivers the architecture, contracts, and data models for all
seventeen differentiators listed in `07-VEYRA-DIFFERENTIATORS.md`; it does
not deliver a working AI assistant — see
`docs/roadmap/PHASE-1-SCOPE.md` for the explicit in/out-of-scope boundary.
