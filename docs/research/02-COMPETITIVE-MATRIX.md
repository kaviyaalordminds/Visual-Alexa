# 02 — Competitive Matrix

Status legend: see `01-LANDSCAPE.md` §0 (VERIFIED / UNKNOWN-NOT-VERIFIED /
DESIGN INFERENCE). Cells below use:

- `YES` — capability confirmed present (VERIFIED)
- `PARTIAL` — capability present in limited/narrow form (VERIFIED, scoped)
- `NO` — capability confirmed absent from the product's documented surface
- `UNK` — UNKNOWN / NOT VERIFIED
- `TARGET` — VEYRA Phase-1+ architectural target (not yet implemented; see
  `docs/roadmap` for sequencing)

Systems compared: Alexa, Siri, Gemini (Assistant), Copilot (incl. Copilot
Vision), Claude "computer use" (capability), OpenAI computer-use agent
(Operator lineage), Project Mariner, Rabbit R1, browser-use-style OSS
agents, and VEYRA's target.

## Full capability matrix

| Capability | Alexa | Siri | Gemini | Copilot/Vision | Claude Computer Use | OpenAI Computer-Use Agent | Project Mariner | Rabbit R1 | OSS Browser Agents | **VEYRA target** |
|---|---|---|---|---|---|---|---|---|---|---|
| Voice input | YES | YES | YES | YES | NO (API capability) | PARTIAL (product-dependent) | NO | YES | NO | **TARGET** |
| Wake word | YES | YES (device-dep.) | PARTIAL | NO | NO | NO | NO | PARTIAL (button-based) | NO | **TARGET** |
| Natural multi-turn conversation | PARTIAL | PARTIAL | YES | YES | YES (via host app) | YES (via host app) | UNK | PARTIAL | NO | **TARGET** |
| Tamil language support | UNK | UNK | PARTIAL (Gemini supports many languages incl. Tamil per Google docs) | UNK | N/A (model, host-dependent) | N/A | UNK | UNK | N/A | **TARGET** |
| Tanglish (code-mixed) support | UNK | UNK | UNK | UNK | N/A | N/A | UNK | UNK | N/A | **TARGET** |
| Screen/visual understanding | NO | NO | PARTIAL (image input) | YES (Copilot Vision) | YES (screenshots) | YES (screenshots) | YES (page render) | UNK | PARTIAL (DOM, not pixels) | **TARGET** |
| Computer control (desktop OS) | NO | NO | NO | PARTIAL (advisory-leaning) | YES (coordinate-based, via dev integration) | YES (hosted/sandboxed) | NO (browser-scoped) | UNK/marketing claim disputed | NO | **TARGET** |
| Keyboard/mouse actuation | NO | NO | NO | UNK | YES (coordinate-based) | YES | NO | UNK | NO | **TARGET** |
| Windows UI Automation / accessibility-API grounding | NO | N/A | UNK | UNK (platform owner, capability plausible) | NO (coordinate-based per docs) | NO (screenshot-based per docs) | N/A | UNK | NO | **TARGET (priority evidence source)** |
| DOM awareness | NO | N/A | UNK | PARTIAL (browser context) | NO (general capability is screenshot-based) | NO (general capability is screenshot-based) | YES | UNK | YES | **TARGET** |
| Browser control | NO | NO | PARTIAL (extension-dependent) | PARTIAL | YES (via tool use) | YES | YES | UNK | YES | **TARGET** |
| File system access | NO | PARTIAL (Shortcuts/Files app scope) | NO | PARTIAL (OS-level, scope evolving) | N/A (sandboxed VM recommended) | N/A (sandboxed) | NO | UNK | NO | **TARGET (capability-scoped)** |
| Application control | PARTIAL (skills) | PARTIAL (App Intents/Shortcuts) | NO | PARTIAL | YES (within sandbox) | YES (within sandbox) | NO | UNK | NO | **TARGET** |
| Persistent cross-session memory | PARTIAL | PARTIAL | YES (Gemini memory feature) | PARTIAL | NO (API capability, stateless per session) | NO | UNK | UNK | NO | **TARGET (structured, inspectable)** |
| Multi-step planning | PARTIAL | PARTIAL | YES | PARTIAL | YES | YES | YES | UNK | PARTIAL | **TARGET** |
| Task verification (did the action actually succeed?) | UNK | UNK | UNK | UNK | PARTIAL (re-screenshot loop) | PARTIAL (re-screenshot loop) | UNK | UNK | PARTIAL | **TARGET (explicit Verify stage)** |
| Task recovery / replanning | UNK | UNK | UNK | UNK | PARTIAL (agent loop can retry) | PARTIAL (agent loop can retry) | UNK | UNK | PARTIAL | **TARGET (explicit Recover stage)** |
| Capability-based permission model | NO (skills perms are coarse OAuth-style) | PARTIAL (App Intents are opt-in per app) | UNK | UNK | PARTIAL (developer-configured tool access) | PARTIAL (confirmation prompts for sensitive actions, per system card) | UNK | UNK | NO (framework-dependent) | **TARGET (first-class, tool-level)** |
| Explicit risk tiers / confirmation UX | NO (documented) | UNK | UNK | UNK | YES (docs recommend confirmation for consequential actions) | YES (docs describe "watch mode" / confirmation for sensitive actions) | UNK | UNK | NO (framework-dependent) | **TARGET (SAFE/MODERATE/SENSITIVE/CRITICAL)** |
| Audit logging (user-visible) | UNK | UNK | UNK | UNK | UNK (host-app responsibility) | UNK (host-app responsibility) | UNK | UNK | NO (framework-dependent) | **TARGET** |
| Local-first execution | NO | PARTIAL (on-device ASR/NLU for some requests) | NO | NO | N/A (sandboxed VM/cloud) | N/A (hosted/cloud) | NO | NO | PARTIAL (runs locally, calls cloud LLM) | **TARGET (default posture)** |
| Offline capability | NO | PARTIAL | NO | NO | NO | NO | NO | NO | NO (needs LLM API) | **TARGET (pluggable local model mode)** |
| Cloud AI option | YES (required) | YES (required for many requests) | YES (required) | YES (required) | YES (required) | YES (required) | YES (required) | YES (required) | YES (required) | **TARGET (optional, provider-agnostic)** |
| External device control (IoT) | YES (mature) | PARTIAL (HomeKit) | YES (mature) | NO | NO | NO | NO | UNK | NO | **TARGET (explicit pair/authorize flow)** |
| Explicit device trust/pairing model | YES (Alexa smart-home skill auth) | YES (HomeKit pairing) | YES (Matter/Google Home) | N/A | N/A | N/A | N/A | UNK | N/A | **TARGET (Matter-inspired, own PC-first)** |
| Avatar / visual identity | NO | NO | NO | PARTIAL (Copilot has a visual mark, not an embodied avatar) | NO | NO | NO | PARTIAL (device persona) | NO | **TARGET (original female AI identity)** |
| Proactive assistance | PARTIAL (routines) | PARTIAL | PARTIAL | PARTIAL | NO | NO | NO | UNK | NO | **Explicitly deferred past Phase 1** |
| Extensibility / plugin architecture | YES (Skills Kit) | PARTIAL (Shortcuts/App Intents) | YES (Extensions) | YES (Plugins/Actions) | YES (developer tool-use API) | YES (developer tool-use API) | UNK | UNK | YES (framework-dependent) | **TARGET (typed Tool Registry)** |
| Workflow automation (user-defined) | PARTIAL (Routines) | PARTIAL (Shortcuts) | UNK | UNK | N/A | N/A | UNK | UNK | N/A | **TARGET (aliases → workflow memory)** |
| Prompt-injection mitigation (documented) | UNK | UNK | UNK | UNK | YES (explicitly documented as an open risk with mitigations) | YES (explicitly documented as an open risk with mitigations) | UNK | UNK | Inconsistent (project-dependent) | **TARGET (first-class threat model, §07)** |

## Reading this matrix

The columns that matter most for VEYRA's product thesis are the three rows
with the strongest external validation: **Task verification**, **Task
recovery**, and **Prompt-injection mitigation**. Both Anthropic and OpenAI's
own official documentation for their computer-use capabilities *independently
converge* on recommending sandboxing, confirmation for consequential actions,
and treating on-screen content as untrusted. No surveyed product turns that
guidance into a first-class, user-facing architecture (risk tiers, an
inspectable permission ledger, an explicit Verify/Recover state machine) —
that gap is VEYRA's primary opportunity and is elaborated in
`07-VEYRA-DIFFERENTIATORS.md`.

See `01-LANDSCAPE.md` for full source notes and verification caveats before
reusing any cell of this table outside this repository.
