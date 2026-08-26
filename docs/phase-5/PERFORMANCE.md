# Performance

Measured, not fabricated, in this environment, 2026-08-26 — brief §70-73's
own "do not claim real-time without measurements."

## 1. What was measured

The full closed-loop voice turn (transcript → normalize → detect language
→ create `Task` → `AgentOrchestrator.run` → `ResponseGenerator`), driven
through the real `VoiceConversationManager` against a real (temp-directory)
filesystem sandbox and real SQLite database
(`tests/integration/test_voice_conversation.py`), consistently completes
within the same low-tens-of-milliseconds range Phase 4's own
`docs/phase-4/PERFORMANCE.md` measured for a bare task run — the voice
layer adds one language-detection pass, one normalization pass, and (at
most) one follow-up-resolution regex pass, all pure Python with no I/O.

## 2. What was not measured, and why

- **Wake word / VAD / STT / TTS latency** — no real implementation of any
  of these exists in this environment (`AUDIO-PIPELINE.md` §3-4); there is
  no audio to time. Reporting a number here would be fabrication.
- **First-partial-transcript / final-transcript timing** — same reason;
  `MockSTT` returns instantaneously by construction, which measures
  nothing about a real STT provider's latency.
- **P50/P95 distributions** — as `docs/phase-4/PERFORMANCE.md` §5 already
  notes for the task engine, a single-process, single-request-at-a-time
  development container doesn't produce a meaningful load distribution.

## 3. Where the time actually goes, in what is measured

`detect_language` and `normalize_command` are both single-pass regex/
string operations over the utterance text — sub-millisecond, the same
order of magnitude as Phase 4's intent classification
(`docs/phase-4/PERFORMANCE.md` §2). The dominant cost in every voice
integration test is identical to Phase 4's own: the real tool call itself
(filesystem I/O, SQLite commits per `TaskStep`) — voice adds no additional
per-step overhead beyond one extra `Message` row write per turn
(`VOICE-PRIVACY.md` §2).

## 4. Streaming responsiveness

`SpeechRecognitionProvider.transcribe`/`SpeechSynthesisProvider.synthesize`
are both `AsyncIterator`-shaped specifically so a real implementation can
begin producing partial transcripts / audio chunks before the full
utterance is available (brief §15/§72) — this shape is real and exercised
by `MockSTT`/`MockTTS`, but no real provider exists yet to measure
first-chunk latency from.

## 5. Honest summary

Everything genuinely measurable in this environment (the pure-logic
pipeline stages, and the full voice-turn-to-Task-outcome loop) is fast and
measured. Everything the brief actually cares about for "real-time voice"
(audio round-trip latency) has no real implementation to measure in this
container — reported here as not measured, not claimed.
