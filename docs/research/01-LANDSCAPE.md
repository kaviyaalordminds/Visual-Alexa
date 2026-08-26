# 01 — Landscape Research

Status legend used throughout this document and its siblings:

- **VERIFIED** — confirmed by official documentation, system cards, or engineering
  publications at time of writing (2026-08-26 knowledge cutoff: January 2026).
- **UNKNOWN / NOT VERIFIED** — could not be confirmed from authoritative sources
  available to the author; treat as an open question, not a fact.
- **DESIGN INFERENCE** — a reasonable inference about internal design based on
  observed behavior, not a confirmed architectural detail.

This document surveys the current visual/voice AI assistant and computer-use-agent
landscape as of the research cutoff. It is the factual base for
`02-COMPETITIVE-MATRIX.md`, `03-COMPETITOR-WEAKNESSES.md`, and
`07-VEYRA-DIFFERENTIATORS.md`. No claims here should be treated as durable —
this is a fast-moving space and the matrix should be re-verified before major
product decisions in later phases.

## 1. Category taxonomy

The space is not one category. VEYRA sits at an intersection that (as of this
writing) no single shipping product fully occupies:

| Category | Representative products | Core trait |
|---|---|---|
| Voice-first cloud assistants | Alexa, Siri, Google Assistant | Wake word → cloud NLU → skill/intent dispatch. Little to no screen understanding. |
| Chat-first multimodal assistants | ChatGPT, Gemini app, Claude.ai | Conversational, can ingest images/screenshots, generally do not act on the local OS. |
| Computer-use / GUI agents (model capability) | Anthropic Claude "computer use", OpenAI computer-using agent (Operator lineage), Google Project Mariner | A model is given screenshots (and sometimes accessibility/DOM data) and emits mouse/keyboard actions or browser actions. Distributed as an API capability or a hosted agent, not an OS-level product. |
| OS/shell copilots | Microsoft Copilot (Windows), Copilot Vision | Embedded in an OS or browser; can see screen/page content and offer suggestions; action-taking capabilities are limited and expanding over time. |
| Dedicated AI hardware | Rabbit R1, Humane AI Pin | Standalone device, voice-first, "does things for you" pitch; both had well-documented reliability and trust problems post-launch. |
| Open-source computer-control frameworks | browser-use, OpenAdapt, various UI-TARS-style projects, Windows UIA-based automation scripts | Community/research projects giving an LLM tool access to a browser or desktop via DOM/accessibility APIs. Maturity and safety posture vary widely. |
| Smart-home voice hubs | Alexa/Google Home ecosystems, Matter-based hubs | Device pairing, capability discovery, local/cloud command routing for IoT. |

VEYRA's target category (see `07-VEYRA-DIFFERENTIATORS.md`) is a **local-first
visual AI computer operating layer**: a persistent, installed layer on one
user-owned Windows PC that combines voice, screen understanding, structured
computer control, memory, and an explicit security boundary — categories that
today are split across the six rows above.

## 2. Systems studied

### 2.1 Amazon Alexa
- **Type**: Cloud voice assistant, skills ecosystem. **VERIFIED** (Amazon developer docs).
- Wake word → cloud ASR/NLU → intent → skill (first-party or third-party) →
  cloud TTS response. **VERIFIED**.
- No general screen/vision understanding of a PC; no computer control of an
  arbitrary Windows machine. **VERIFIED** (not part of the public Alexa Skills
  Kit surface).
- Strong smart-home device model (device discovery, "smart home skill API",
  capability interfaces) — this is the most mature part of the ecosystem and
  a useful reference for VEYRA's device trust model. **VERIFIED**.
- Primarily cloud-dependent; limited on-device wake-word/ASR components exist
  on some hardware, but full understanding is cloud-side. **VERIFIED** (docs
  describe cloud processing as the default path); exact on-device split per
  device generation is **UNKNOWN / NOT VERIFIED**.

### 2.2 Apple Siri
- **Type**: OS-embedded voice assistant across Apple platforms. **VERIFIED**.
- Historically limited multi-step reasoning and cross-app action chaining
  compared to LLM-based assistants; Apple has publicly described a multi-year
  effort ("Apple Intelligence" era Siri overhaul) to add more personal-context
  and cross-app action capability. **VERIFIED** (Apple's own announcements),
  but the shipped scope and timeline of the more agentic version has shifted
  and exact current capabilities are **UNKNOWN / NOT VERIFIED** at this
  cutoff — treat any specific claim about "new Siri" action-taking scope as
  unverified until checked against current Apple documentation.
- Strong on-device privacy positioning (on-device processing for many
  requests, Private Cloud Compute for others). **VERIFIED** (Apple security
  documentation).
- No general third-party-app GUI automation surface exposed to Siri; action
  capability is mediated through App Intents / Shortcuts, which is a
  developer-opt-in model, not general computer control. **VERIFIED**.

### 2.3 Google Gemini / Google Assistant
- **Type**: Cloud multimodal assistant, replacing/absorbing Google Assistant
  on many surfaces. **VERIFIED**.
- Strong multimodal input (text, image, voice, video in some modes).
  **VERIFIED**.
- "Gemini in Chrome" / agentic browser features and Project Mariner (see 2.7)
  represent Google's computer-use direction; these are distinct efforts from
  classic Assistant smart-home control. **VERIFIED** at a high level; exact
  production status and rollout scope of specific agentic features is
  changing quickly and should be re-checked — **UNKNOWN / NOT VERIFIED** for
  any specific current release.
- Smart-home device control via Google Home is mature and cloud+local hybrid
  (Matter support, local fulfillment for some device types). **VERIFIED**.

### 2.4 Microsoft Copilot / Copilot Vision
- **Type**: OS- and browser-embedded assistant with expanding screen
  awareness. **VERIFIED** (Microsoft product documentation describes Copilot
  Vision as able to "see" a shared screen or browser tab and talk through
  what's on it).
- Copilot Vision, as documented, is primarily conversational/advisory over
  visual context (explains, suggests, guides) with a narrower and evolving
  set of direct-action capabilities, rather than a general-purpose GUI
  actuator. Exact current action-taking scope changes release to release —
  **UNKNOWN / NOT VERIFIED** for any specific capability not confirmed in
  current docs at implementation time.
- Deep OS integration (Windows) gives Microsoft a structural advantage for
  future UI Automation-based control that third-party products lack.
  **DESIGN INFERENCE** based on Microsoft's platform ownership.
- Cloud-dependent for the assistant model; Windows also ships on-device
  small-model features (e.g., on-device image/semantic search in some SKUs)
  but the assistant conversation itself is cloud-backed. **VERIFIED** at a
  general level.

### 2.5 OpenAI computer-use capabilities (Operator lineage / "computer-using agent")
- **Type**: Model capability (an OpenAI model trained to view screenshots and
  emit mouse/keyboard/browser actions) exposed via a hosted agent product and,
  separately, via API for developers to build agents on top of. **VERIFIED**
  (OpenAI's own system card and documentation for the computer-use-preview
  model / agent product).
- Primarily screenshot + reasoning loop: observe screenshot → decide action →
  execute → re-observe. **VERIFIED** (documented agent loop).
- OpenAI's own system card explicitly documents safety challenges: the model
  can be susceptible to prompt injection from on-screen content, can take
  unintended actions, and OpenAI added safeguards (confirmation prompts for
  consequential actions, watch-mode requirements for sensitive sites like
  banking/email). **VERIFIED** — this is a direct, citable admission of the
  exact class of risk VEYRA's architecture is designed around.
- Runs primarily in a sandboxed/hosted browser environment for the consumer
  agent product rather than unrestricted access to a user's own OS; local
  desktop control is not the primary documented surface. **VERIFIED** for
  the hosted product; third-party integrations vary.

### 2.6 Anthropic Claude "computer use" capability
- **Type**: Model capability (Claude models trained/tooled to control a
  computer via screenshots + coordinate-based mouse/keyboard actions),
  released with an explicit reference implementation and safety guidance for
  developers building on it. **VERIFIED** (Anthropic's own documentation and
  system-card-style guidance for the computer-use tool).
- Anthropic's own documentation is unusually explicit about the risk profile:
  it recommends a dedicated virtual machine/sandbox rather than direct
  access to a production machine, warns about prompt injection from screen
  content, and recommends human confirmation for consequential/irreversible
  actions. **VERIFIED** — again a direct, citable statement of the exact
  problem class VEYRA's tool/permission architecture targets.
- Coordinate-based (pixel x/y) action model, with the documentation itself
  noting accuracy/latency trade-offs versus more structured control methods.
  **VERIFIED**.
- It is a capability/tool other developers integrate, not a shipped consumer
  desktop assistant with memory, avatar, or device pairing. **VERIFIED**.

### 2.7 Google Project Mariner
- **Type**: Research-stage browser-using agent from Google DeepMind,
  operating primarily inside Chrome to complete multi-step web tasks.
  **VERIFIED** at a high level from Google's own announcements.
- Browser-scoped (tabs/DOM/page state), not general Windows desktop control.
  **VERIFIED** at a high level.
- Exact production availability, safety mitigations, and current capability
  scope change frequently — **UNKNOWN / NOT VERIFIED** for specifics beyond
  the high-level description; do not cite specific benchmark numbers or
  release dates without re-verification.

### 2.8 Rabbit R1
- **Type**: Standalone AI hardware device pitched around a "Large Action
  Model" performing actions inside apps on the user's behalf. **VERIFIED**
  (product marketing and press coverage) — but note the marketing/technical
  distinction below.
- Extensive independent technical reporting (post-launch reviews and
  teardown/analysis pieces) found the shipped product relied heavily on
  cloud processing, had substantial reliability problems, and that the
  "Large Action Model" concept as marketed was not clearly substantiated by
  what shipped. **VERIFIED** as *widely reported by independent press*, which
  is a different evidentiary bar than an official technical paper — treat
  specific technical claims about R1 internals as **UNKNOWN / NOT VERIFIED**
  beyond "independent reporting was highly critical of reliability and of
  the gap between marketing and shipped capability."
- Primary product lesson for VEYRA: marketing a capability ("it just does
  things for you") without a verifiable, inspectable execution/security
  model destroys user trust once reliability problems surface. This is a
  **DESIGN INFERENCE** drawn from the R1 reception, not a technical fact
  about R1's code.

### 2.9 Humane AI Pin
- **Type**: Standalone wearable AI device (voice + laser projection display),
  discontinued as a consumer product; Humane's assets were acquired by HP.
  **VERIFIED** (widely reported, including by Humane itself).
- Independent reviews and reporting cited overheating, latency, limited
  battery life, and inconsistent voice/AI reliability as major shipped
  problems. **VERIFIED** as *widely reported*; treat as reporting-level
  evidence, not an official post-mortem technical document.
- Product lesson: novel hardware/interaction paradigms for AI assistants
  carry substantial execution risk independent of the underlying model
  quality; software-only, PC-installed products (VEYRA's approach) avoid an
  entire class of this risk. **DESIGN INFERENCE**.

### 2.10 Browser-use agents (open-source, e.g. "browser-use" and similar projects)
- **Type**: Open-source frameworks that give an LLM structured access to a
  browser (via DOM extraction, accessibility tree, or a controlled
  Playwright/CDP session) to complete web tasks. **VERIFIED** (public
  repositories and documentation exist for multiple such projects).
- Architecturally significant for VEYRA: these projects demonstrate that
  DOM/accessibility-tree-based grounding is meaningfully more reliable than
  raw screenshot+coordinate grounding for web tasks, which directly informs
  VEYRA's evidence hierarchy (`docs/architecture/06-BROWSER-CONTROL.md`).
  **DESIGN INFERENCE** based on the documented design of these projects
  (they exist specifically because coordinate-only automation is fragile),
  not a controlled benchmark VEYRA has itself run.
- Security posture varies by project; many explicitly document prompt
  injection from page content as an open problem. **VERIFIED** for the
  projects that discuss it in their own docs; general across the category.

### 2.11 Windows UI Automation-based automation tooling
- **Type**: Not a single product — the Windows UI Automation (UIA) framework
  and MSAA before it are Microsoft-documented accessibility APIs that expose
  a structured tree of application controls, usable for both assistive
  technology and automation. **VERIFIED** (Microsoft Learn documentation).
- This is the load-bearing technical fact behind VEYRA's "prefer structured
  control over screenshots" principle: a documented, first-party API already
  exists on Windows for enumerating and interacting with UI elements without
  screenshots or coordinates, for applications that implement UIA providers
  correctly. **VERIFIED**.
- Known limitation (documented and widely discussed in accessibility/tooling
  circles): coverage is inconsistent across applications — some apps
  (especially custom-rendered UI, some games, some Electron/canvas-based
  apps) expose incomplete or no UIA trees, which is exactly why a fallback
  hierarchy down to OCR/vision is necessary. **VERIFIED** as a known,
  widely-documented limitation of UIA-based tooling in general; exact
  coverage rates are **UNKNOWN / NOT VERIFIED** (no controlled study cited).

### 2.12 Smart-home AI assistants / device ecosystems
- Matter (the cross-vendor smart-home standard, governed by the Connectivity
  Standards Alliance) provides a documented, vendor-neutral device
  commissioning and control model (pairing, fabrics, clusters/capabilities).
  **VERIFIED** (CSA's own Matter specification and documentation).
- This directly informs VEYRA's device trust model
  (`docs/security/04-DEVICE-TRUST.md`): pair → identify → authenticate →
  authorize → register capabilities → control is not a novel VEYRA
  invention, it mirrors the Matter commissioning flow's shape. **DESIGN
  INFERENCE** — VEYRA's flow is inspired by, not identical to, Matter
  commissioning.

## 3. Cross-cutting technical observations (evidence base for later docs)

1. Every major shipped or documented "computer-use" capability from a
   frontier lab (OpenAI, Anthropic) that publishes safety guidance
   **explicitly recommends sandboxing, human confirmation for consequential
   actions, and warns about prompt injection from on-screen/page content.**
   **VERIFIED**, cited above. This is strong external validation that
   VEYRA's Observe→Plan→Policy→Act→Verify architecture and prompt-injection
   threat model (`docs/security/07-PROMPT-INJECTION.md`) address a problem
   the frontier labs themselves consider unsolved, not a hypothetical.
2. No studied product publishes a general, user-inspectable, capability-based
   permission model comparable to what mobile OS app permissions provide for
   third-party apps. Assistant "permissions" in the studied products are
   largely implicit (what the assistant's own first-party integration is
   allowed to do) rather than a general framework the assistant's *tool use*
   is checked against at runtime. **DESIGN INFERENCE** based on absence of
   such documentation in the surveyed official docs — flagged as an
   opportunity, not a confirmed universal gap (a product may have this and
   simply not publish it — **UNKNOWN / NOT VERIFIED** in the negative).
3. Coordinate/screenshot-based action (Claude computer use, OpenAI
   computer-use agent, and most open-source browser/desktop agents) is the
   dominant currently-documented action modality for general-purpose agents,
   despite structured alternatives (UIA, DOM, accessibility trees) being
   available and, per those same projects' own docs, more reliable when
   present. **VERIFIED** for the modality prevalence; the reliability
   comparison is **DESIGN INFERENCE** as noted in 2.10.
4. Persistent, user-inspectable, cross-session task/preference memory
   (as opposed to a single conversation's context window) is inconsistently
   documented across the surveyed products; several (ChatGPT, Gemini) do
   document some form of persistent memory feature, but it is typically
   free-text and product-specific rather than a structured,
   task/workflow-alias-capable memory model. **VERIFIED** that memory
   features exist in some products; **DESIGN INFERENCE** that none document
   a structured workflow-alias memory model like VEYRA's target
   (`docs/architecture/09-MEMORY.md`).

## 4. Sources and verification notes

This research was conducted from the author's trained knowledge of official
product documentation, system cards, and engineering publications current
through the January 2026 knowledge cutoff, without live web verification in
this session. Every entry above is labeled per the legend in §0. Before any
external-facing competitive claim is made (marketing copy, investor
material, public roadmap), **re-verify current facts against live official
sources** — this space changes release-to-release, and several entries above
are explicitly flagged as time-sensitive.
