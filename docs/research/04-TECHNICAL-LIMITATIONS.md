# 04 — Technical Limitations of the Current Landscape

Distilled from `01-LANDSCAPE.md` and `03-COMPETITOR-WEAKNESSES.md`, organized
by technical subsystem rather than by product. This is the document to read
when designing a specific VEYRA subsystem and wanting to know "what should we
specifically avoid repeating."

## Grounding / UI understanding
- Screenshot + pixel-coordinate grounding is the dominant modality for
  general-purpose computer-use agents (Claude computer use, OpenAI
  computer-use agent), despite documented accuracy/latency trade-offs.
- Structured grounding (UI Automation, accessibility tree, DOM) exists and is
  used successfully in narrower-scope tools (OSS browser agents) but is not
  the default for cross-application desktop control in any surveyed
  general-purpose product.
- **VEYRA response**: `docs/architecture/05-COMPUTER-CONTROL.md` mandates an
  evidence hierarchy that only falls back to vision/coordinates when
  structured sources are unavailable.

## Verification
- The dominant verification pattern is "take another screenshot and let the
  same model re-interpret it" — a closed loop with no independent check.
- No surveyed product publishes a distinct, typed "verify expected postcondition"
  step separate from general re-observation.
- **VEYRA response**: explicit VERIFYING task state
  (`docs/architecture/14-TASK-LIFECYCLE.md`) with per-tool verification
  strategies declared in the Tool Registry (`docs/architecture/04-TOOL-ARCHITECTURE.md`).

## Permissions and sandboxing
- Anthropic's documented mitigation for computer-use risk is environment
  isolation (a dedicated VM), i.e., scoping the *machine*, not the *agent's
  capabilities within the machine*.
- Neither frontier-lab computer-use capability publishes a granular,
  per-tool, expiring, revocable permission-grant model.
- **VEYRA response**: capability-based permissions scoped to the *tool call*,
  not the machine (`docs/security/02-PERMISSION-MODEL.md`), so VEYRA can run
  on the user's real, primary PC without requiring a throwaway VM, while
  still bounding blast radius.

## Task planning and state
- Documented agent loops (Claude/OpenAI computer use) are largely flat
  observe-act loops bounded by step count/timeout, without a published
  explicit state machine exposing intermediate states (planning, waiting for
  permission, recovering) to the host application or the user.
- **VEYRA response**: explicit `TaskState` enum
  (`docs/architecture/14-TASK-LIFECYCLE.md`) driving both execution logic and
  UI/avatar state, so the user always knows which phase a task is in.

## Memory
- Persistent memory features that exist (Gemini, ChatGPT) are largely
  free-text personalization, not structured, typed, revocable memory records
  with distinct categories.
- **VEYRA response**: `docs/architecture/09-MEMORY.md` defines seven memory
  categories, all user-inspectable/editable/deletable, none hidden.

## Multilingual / code-mixed voice
- No surveyed product publishes verified Tanglish (Tamil-English code-mixed)
  conversational accuracy data.
- **VEYRA response**: `docs/architecture/08-VOICE.md` treats language
  detection as a distinct pluggable stage (not baked into a single STT
  model choice), so Tamil/Tanglish support can be iterated independently and
  benchmarked empirically rather than assumed.

## Browser automation
- Coordinate-based browser automation (clicking at pixel positions inside a
  rendered page) is fragile to layout/zoom/responsive changes; DOM-based
  browser agents (OSS projects) are measurably more robust in their own
  documented design rationale.
- **VEYRA response**: `docs/architecture/06-BROWSER-CONTROL.md` mandates
  DOM/accessibility-first browser control via a dedicated extension/CDP
  bridge, with coordinate clicking as an explicit last resort only.

## IoT / device control
- Mature ecosystems (Alexa, Google Home, HomeKit, Matter) already solve
  device pairing/authorization well; this is not a gap to "fix," it's a
  pattern to adopt.
- General-purpose computer-use agents have no IoT surface at all.
- **VEYRA response**: `docs/architecture/10-IOT.md` adopts a
  Matter-commissioning-inspired pair→authorize→register→control flow rather
  than inventing a new device trust model from scratch.

## Cloud dependency / offline capability
- Every surveyed conversational assistant requires a cloud round-trip for
  core reasoning; none document a fully offline mode with equivalent
  capability.
- **VEYRA response**: `docs/architecture/03-AI-ARCHITECTURE.md` and
  `docs/roadmap` define LOCAL / HYBRID / CLOUD modes as a first-class,
  provider-agnostic architectural axis, not a stretch goal bolted on later.
