# 08 — Unsolved Problems

Problems the landscape research surfaced that VEYRA does **not** claim to
solve in Phase 1, or at all yet. Listed honestly so later phases don't
accidentally overclaim.

## Genuinely open industry-wide problems
1. **Reliable UI grounding on applications with no accessibility tree**
   (custom-rendered UI, canvas/game UIs, some Electron apps). The evidence
   hierarchy degrades to OCR/vision for these — which inherits all the
   fragility problems documented in `03-COMPETITOR-WEAKNESSES.md`. VEYRA's
   architecture routes around this where possible; it does not solve it.
2. **Tanglish (code-mixed Tamil-English) conversational voice accuracy** —
   no verified benchmark exists industry-wide. VEYRA's pluggable
   architecture lets this be iterated and measured, but Phase 1 does not
   claim any Tanglish accuracy number.
3. **Safe automation of login / OTP / CAPTCHA flows.** Genuinely hard: it
   intersects account security, third-party ToS, and anti-automation
   defenses designed specifically to stop this. VEYRA explicitly excludes
   this from scope rather than pretending to have a safe answer.
4. **Prompt injection from untrusted content is mitigated, not eliminated.**
   Treating observed content as data instead of instructions
   (`docs/security/07-PROMPT-INJECTION.md`) reduces but does not
   provably eliminate the risk class — this remains an open research problem
   across the entire industry, VEYRA included.
5. **Cross-application semantic understanding without per-app integration.**
   A generic UIA/DOM/OCR pipeline can locate elements; it cannot always
   understand *what a workflow inside an unfamiliar application means*.
   Deep reliability for a given app benefits from app-specific integration
   work that scales linearly with the number of supported apps.
6. **Latency of local models vs. cloud models.** Local-first is a privacy
   and reliability win, but local models capable of complex planning are
   presently slower/weaker than frontier cloud models on constrained
   consumer hardware. HYBRID mode exists precisely because this trade-off
   has no universal answer.
7. **Distinguishing a legitimately ambiguous request from a legitimately
   confident one at scale.** The Phase 1 architecture defines the contract
   (ask when ambiguous); tuning the actual confidence thresholds against
   real user tolerance for interruption is an empirical problem for later
   phases, not something architecture alone resolves.
8. **Original, appealing avatar/character design that reads as distinct
   from existing assistants while remaining broadly appealing** is a design
   problem, not just an engineering one, and is explicitly deferred past
   Phase 1.

## Explicitly deferred by scope (not "unsolved," just "not yet attempted")
- Full autonomous multi-step computer control
- Full voice pipeline (STT/TTS integration)
- Full vision pipeline (live screen understanding)
- WhatsApp automation
- Full IoT device drivers
- Remote access / cross-device control
- Final avatar assets and animation

These are listed here, not as failures, but so Phase 2+ planning starts from
an accurate list of what genuinely remains — see `docs/roadmap`.
