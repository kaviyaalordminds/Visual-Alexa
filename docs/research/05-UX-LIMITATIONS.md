# 05 — UX Limitations of the Current Landscape

## No visible "what is it doing right now" state
Most voice assistants collapse to a single listening/thinking animation
(e.g., a pulsing light or waveform) with no differentiated states for
planning vs. executing vs. waiting on a risky confirmation. Users cannot
tell, from the UI alone, whether the assistant is "thinking" or "about to do
something irreversible."
**VEYRA response**: an explicit avatar/UI state machine (IDLE, LISTENING,
THINKING, PLANNING, EXECUTING, WAITING_CONFIRMATION, SUCCESS, WARNING, ERROR,
SPEAKING — product brief §16, `docs/architecture/02-DESKTOP-ARCHITECTURE.md`)
tied 1:1 to the backend task state machine via the event bus, so visual state
is never decorative — it reflects real execution state.

## Confirmation fatigue vs. silent risk
Products either under-confirm (frontier labs' own docs cite this as a risk
they had to retrofit mitigations for) or, in more conservative integrations,
over-confirm every trivial action, training users to reflexively tap
"allow." Neither is good UX.
**VEYRA response**: risk-tiered confirmation (SAFE/MODERATE/SENSITIVE/
CRITICAL, product brief §9) means only actions that warrant interruption
interrupt the user, with SENSITIVE actions supporting configurable
confirmation policy per user preference rather than one global setting.

## No inspectable permission/action history
Users of mainstream assistants generally cannot see a structured log of
"what did the assistant do, with what tool, under what permission, and did
it succeed" — at best there is a conversational transcript.
**VEYRA response**: `docs/security/06-AUDIT-LOGGING.md` treats the audit log
as a user-facing feature, not just an internal debugging aid.

## Guessing instead of asking under ambiguity
When faced with "send it to Arun" and multiple contacts named Arun, the
default behavior in many automation-style flows (Shortcuts, Routines, and
inferred behavior of less conservative agent loops) is to pick the most
recently used or highest-ranked match rather than asking. This is efficient
but erodes trust the first time it's wrong for anything consequential.
**VEYRA response**: ambiguity resolution is a named planner responsibility
(product brief §6.7), tested explicitly in the agent-eval suite
(`tests/agent-evals`).

## No durable, user-editable "what I meant by that" aliases
Voice assistants support routines/shortcuts (trigger → fixed action), but
not general referential aliases usable inside arbitrary future commands
("office folder" → `D:\Projects\Office`, reusable in any sentence, not just
a fixed trigger phrase).
**VEYRA response**: workflow memory (`docs/architecture/09-MEMORY.md`) is
designed for exactly this pattern.

## Generic or absent visual identity
Voice-only assistants have no embodied presence; assistants with a visual
mark (Copilot's orb, etc.) have a brand mark, not an emotionally legible
character with task-state expressions.
**VEYRA response**: original avatar architecture (product brief §16),
explicitly required to avoid resembling any existing assistant identity.

## Round-trip latency breaking conversational flow
Cloud-dependent voice loops introduce a network round trip on every turn,
which is felt as "the assistant is slow to respond" even when the model
itself is fast.
**VEYRA response**: real-time path vs. background path separation
(`docs/architecture/13-DATA-FLOW.md`) keeps voice-critical work off any path
that could be blocked by indexing/embedding/maintenance work.

## No language switch tolerance mid-sentence
Tamil-English speakers naturally code-mix ("andha file-a open pannu"); rigid
single-language ASR/NLU pipelines penalize this by misrecognizing or
rejecting mixed input.
**VEYRA response**: `docs/architecture/08-VOICE.md` treats Tanglish as a
first-class design target for the language-detection stage, not an
afterthought bolted onto an English-first pipeline.
