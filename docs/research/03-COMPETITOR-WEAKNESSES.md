# 03 — Competitor Weaknesses

Status legend: see `01-LANDSCAPE.md` §0. Each weakness below is tagged:

- **CONFIRMED LIMITATION** — directly stated or clearly demonstrated in
  official documentation, system cards, or the product's own published
  guidance.
- **DESIGN INFERENCE** — a reasonable architectural inference from documented
  behavior/design, not itself directly published as a limitation.
- **OPEN QUESTION** — genuinely unresolved; flagged for re-research before
  being used as a product claim.

## 1. Screen understanding without direct action
**CONFIRMED LIMITATION** (Copilot Vision, per Microsoft's own product
description, is primarily conversational/advisory over visual context with
narrower and evolving direct-action scope). This is a real, documented
product-tier split between "can see" and "can act," and it means a large
class of shipped products cannot close the loop from observation to
execution without a separate mechanism.

## 2. Direct action without reliable verification
**DESIGN INFERENCE.** Both Claude computer-use and OpenAI's computer-use
agent operate an observe→act→re-observe loop (re-screenshot after each
action), which is a *form* of verification, but neither publishes a
structured, typed "did the intended state change occur" verification step
distinct from "take another screenshot and let the model re-interpret it."
Re-interpretation by the same model that just acted is weaker evidence than
an independent verification check (e.g., re-querying UI Automation for the
expected element state). VEYRA's explicit Verify stage
(`docs/architecture/14-TASK-LIFECYCLE.md`) is designed against this gap.

## 3. Coordinate-based automation
**CONFIRMED LIMITATION**, self-documented. Anthropic's own computer-use
documentation describes pixel-coordinate mouse actions and separately notes
accuracy/latency trade-offs. Coordinate actions break when window position,
DPI scaling, resolution, or layout changes — a maintenance burden that
structured control (UI Automation IDs, DOM selectors) does not have.

## 4. Fragile UI interaction
**DESIGN INFERENCE**, directly following from #3: any coordinate- or
pure-vision-grounded action model degrades when an application updates its
UI, changes a button's position, or renders at a different DPI/theme. This
is a known class of problem in the broader RPA (robotic process automation)
industry, which VEYRA's evidence hierarchy (native API → UIA → accessibility
tree → DOM → OCR → vision → coordinates as last resort) is explicitly
designed to avoid defaulting into.

## 5. Poor recovery after UI changes
**OPEN QUESTION** for the specific frontier-lab products (no published
failure-mode statistics available to this research). **DESIGN INFERENCE**
generally: an agent with no explicit "recognize the UI changed, replan"
state is structurally more likely to retry the same failing coordinate
action or hallucinate a plausible-looking but wrong element. VEYRA's task
state machine includes an explicit RECOVERING state precisely to force this
decision point (`docs/architecture/14-TASK-LIFECYCLE.md`).

## 6. Hallucinated UI elements
**CONFIRMED LIMITATION** as a general vision-language-model failure mode
(documented broadly in VLM grounding research; not specific to one vendor).
A model asked "click the Submit button" from a screenshot can report high
confidence about a button that does not exist or is at the wrong coordinates.
This is precisely why VEYRA treats vision-model grounding as low-priority
evidence, behind structured APIs, and requires confidence-aware execution
(`docs/architecture/03-AI-ARCHITECTURE.md`, §confidence).

## 7. Wrong application / wrong contact selection
**DESIGN INFERENCE.** No surveyed product publishes an explicit "ambiguity
detected, ask the user" contract for the general case of "there are two
things named X, which one?" Alexa/Siri/Assistant handle a narrow version of
this for contacts via disambiguation prompts in some flows (**CONFIRMED
LIMITATION** that this is *not* universal across all action types), but
general computer-use agents have no documented general ambiguity-resolution
contract. VEYRA makes ambiguity resolution a first-class planner behavior
(§6.7 of the product brief; `docs/architecture/03-AI-ARCHITECTURE.md`).

## 8. Insufficient confirmation for consequential actions
**CONFIRMED LIMITATION historically, being actively addressed.** Both
Anthropic and OpenAI's own documentation for their computer-use capabilities
explicitly call out under-confirmation of consequential actions as a risk
they added mitigations for (confirmation prompts, "watch mode" for sensitive
sites). The fact that frontier labs had to retrofit this is direct evidence
that it is not a solved problem, and is the strongest external validation
for VEYRA building risk-tiered confirmation in from the start rather than as
an afterthought (`docs/security/08-SENSITIVE-ACTION-POLICY.md`).

## 9. Over-permissioned agents
**DESIGN INFERENCE**, informed by Anthropic's own documentation recommending
a dedicated sandboxed VM (i.e., *not* the user's real machine) for computer
use precisely because the alternative — the agent's tool having the same
access as the human operator — is considered too risky for general use.
That recommendation is itself an admission that the natural/default
integration (agent = full user access) is over-permissioned. VEYRA's
capability-based, tool-scoped permission model
(`docs/security/02-PERMISSION-MODEL.md`) is designed to make "sandboxed VM"
unnecessary by scoping the *agent's* access, not the *machine's* access.

## 10. Weak auditability
**OPEN QUESTION** for most surveyed products — audit logging for
assistant/agent actions is largely unpublished (host-app or
integration-dependent for API-level capabilities like Claude/OpenAI computer
use). Absence of published detail is not proof of absence, so this is
flagged as an open question, not a confirmed gap. VEYRA treats
audit logging as an architectural requirement regardless
(`docs/security/06-AUDIT-LOGGING.md`), because "no evidence a competitor
does this well" is itself sufficient reason to build it deliberately.

## 11. Cloud dependency
**CONFIRMED LIMITATION**, broadly, across nearly every surveyed product:
Alexa, Siri (for many request types), Gemini, Copilot, Claude computer use,
and OpenAI's computer-use agent all require a cloud round-trip for the
core reasoning step. This is the single most consistent weakness across the
entire landscape and directly motivates VEYRA's local-first default posture.

## 12. Privacy concerns from continuous visual/audio observation
**DESIGN INFERENCE**, industry-wide: any product with "see your screen" or
"always listening" capability creates an inherent continuous-observation
privacy question. Products vary in mitigations (Siri/Apple's on-device
processing emphasis is the strongest documented counter-example). VEYRA's
adaptive observation strategy and explicit mic/screen-off-by-default posture
(`docs/security/05-DATA-PROTECTION.md`) directly targets this.

## 13. Poor local-first behavior
**CONFIRMED LIMITATION**, same evidence as #11 — "local-first" is not the
default design center of any major surveyed assistant.

## 14. Lack of persistent, structured, user-editable memory
**DESIGN INFERENCE.** Some products (Gemini, ChatGPT more broadly) do
publish a "memory" feature, but it is typically free-text personalization
rather than a structured, inspectable, workflow-alias-capable memory model
with distinct categories (task, preference, semantic, workflow, device).
No surveyed product documents anything resembling VEYRA's target memory
architecture (`docs/architecture/09-MEMORY.md`).

## 15. Session-only visual context
**DESIGN INFERENCE.** Screenshot-driven computer-use loops (Claude, OpenAI)
are documented as operating within a bounded task/session context; there is
no published cross-session "the assistant remembers what your desktop
usually looks like" capability. This limits reliability of future
disambiguation ("open my usual browser window layout") without VEYRA-style
persistent task/device memory.

## 16. Poor multilingual voice support, esp. Tamil / Tanglish (code-mixed)
**OPEN QUESTION.** Google documents broad language support for Gemini
including Tamil at a text/translation level, but code-mixed
Tamil-English ("Tanglish") conversational voice support is not something
any surveyed product publishes explicit, verified accuracy claims about.
This is flagged as a genuine open question requiring direct empirical
testing in a later phase (voice architecture design accounts for this via
a pluggable STT/language-detection layer — `docs/architecture/08-VOICE.md`).

## 17. Slow voice interaction / round-trip latency
**DESIGN INFERENCE.** Cloud-round-trip voice assistants inherently carry
network latency in the wake-word→ASR→NLU→TTS loop. VEYRA's separation of a
real-time path from a background path (`docs/architecture/13-DATA-FLOW.md`)
is designed to bound this, but no specific competitor latency numbers are
cited here (**UNKNOWN / NOT VERIFIED** for exact figures).

## 18. Robotic / non-expressive TTS
**OPEN QUESTION.** TTS quality has improved substantially industry-wide and
specific current-generation comparisons are **UNKNOWN / NOT VERIFIED**
without direct testing; not treated as a stable competitive claim.

## 19. Lack of emotional/visual identity ("just a voice" or generic mark)
**CONFIRMED LIMITATION** for the voice-first assistants (Alexa, Siri, Google
Assistant have no embodied visual avatar in mainstream product surfaces) and
**DESIGN INFERENCE** for Copilot (has a visual mark/orb, not an embodied,
emotionally-stateful avatar). This is a clear, low-risk differentiation
space for VEYRA (`docs/architecture/*avatar*` and product brief §16),
provided VEYRA does not copy any existing assistant's visual identity.

## 20. Lack of continuous, structured task context across turns
Covered under #15.

## 21. Lack of user-defined workflows / weak plugin architecture (general agents)
**CONFIRMED LIMITATION** for the frontier-lab computer-use *capabilities*
specifically (they are developer tool-use APIs, not end-user
workflow-authoring products) and **PARTIAL** for the voice assistants
(Alexa Routines, Siri Shortcuts exist but are trigger-action automations,
not general "remember what I mean when I say X" alias/workflow memory).

## 22. Weak IoT authorization / no explicit device-trust model (general agents)
**CONFIRMED LIMITATION** for the computer-use capability products (no IoT
control surface at all) and **N/A-not-a-weakness** for the mature smart-home
platforms (Alexa, Google Home, HomeKit all have real pairing/auth models —
this is their strength, not weakness, and VEYRA's device trust model is
explicitly informed by them, not claiming to beat them at IoT).

## 23. No capability-based permissions for agent tool use
**DESIGN INFERENCE**, consistent with #9: developer-configured tool access
(Claude/OpenAI computer-use APIs) is a coarser, deploy-time decision, not a
runtime, per-action, typed capability grant with expiration/revocation like
VEYRA's `PermissionGrant` model (`docs/security/02-PERMISSION-MODEL.md`).

## 24. Poor task recovery generally
Covered under #5.

## 25. Lack of deterministic tools / excessive reliance on vision models
**CONFIRMED LIMITATION**, same evidence as #3/#6: coordinate/screenshot
grounding is the *documented default* modality for the highest-profile
computer-use capabilities, despite more deterministic alternatives (UIA,
DOM) existing and being used by narrower-scope OSS browser agents.

## 26. Lack of structured Windows UI Automation usage
**CONFIRMED LIMITATION** for Claude/OpenAI's public computer-use
documentation (both describe screenshot+coordinate grounding, not UIA
integration). Microsoft's own Copilot may have platform-level access to
this (**UNKNOWN / NOT VERIFIED**, not publicly detailed), but no
surveyed *cross-platform* agent capability documents UIA-first grounding.

## 27. Lack of DOM/accessibility awareness (desktop, not just browser)
Covered under #26; browser-scoped OSS agents (browser-use-style projects) do
use DOM, which is why VEYRA extends the same principle to the Windows
desktop rather than treating it as browser-only.

## 28. Poor handling of login / OTP / CAPTCHA flows
**OPEN QUESTION**, generally under-documented across all surveyed products,
and inherently sensitive (agents automating OTP/CAPTCHA flows raises
platform ToS and security questions beyond VEYRA's Phase 1 scope). VEYRA's
Phase 1 explicitly excludes credential extraction and any CAPTCHA-defeat
behavior (`docs/security/01-SECURITY-ARCHITECTURE.md`).

## 29. Poor handling of ambiguity
Covered under #7.

## 30. Poor handling of destructive actions
**CONFIRMED LIMITATION** as a risk class (this is precisely why Anthropic
and OpenAI both added consequential-action confirmation, per #8) even though
neither vendor publishes failure statistics. VEYRA's CRITICAL risk tier with
mandatory explicit confirmation (`docs/security/08-SENSITIVE-ACTION-POLICY.md`)
is the direct architectural response.

## Summary

The weaknesses with the strongest evidentiary support (self-documented by
the frontier labs themselves) are #3 (coordinate-based fragility), #8
(under-confirmation of consequential actions), #9 (over-broad agent
permissions), and #11 (cloud dependency). These four are treated as the
highest-confidence, lowest-risk differentiation targets for VEYRA and are
elaborated with concrete architecture in `07-VEYRA-DIFFERENTIATORS.md` and
`docs/security/`.
