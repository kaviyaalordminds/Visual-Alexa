# Lip Sync

## 1. There is no real audio to sync to

`docs/phase-5/PHASE-5-TEST-RESULTS.md` §5 established this and it hasn't
changed: no audio hardware, no audio library, no real TTS backend exists
in this environment. There is no waveform, no phoneme timing, nothing a
real lip-sync system would normally read.

## 2. What ships instead, and why it's still real

`services/voice/voice/core/visemes.py`'s `text_to_visemes` is a
deterministic, stdlib-only function: it classifies every letter of the
*actual* response text into one of ten mouth-shape buckets
(`VisemeShape`) and lays the classified letters out along a synthetic
timeline at a fixed speaking rate, merging consecutive same-bucket
letters into one held frame and inserting a short rest between words.

It is real in three concrete senses: it always reflects the real text
being spoken (never a placeholder), it always produces a genuine,
reproducible timeline (same text -> same output, unit-tested), and the
avatar-rendering layer consumes it through exactly the shape
(`VisemeFrame: {shape, start_ms, duration_ms}`) a future real TTS backend
would supply real phoneme timings through — nothing downstream needs to
change if that backend arrives.

It is explicitly *not* real in one sense, stated plainly rather than
implied: the timing is a fixed-rate approximation, not measured from
actual speech, so it will not sync to a real human or TTS voice's actual
cadence. This is the same honesty Phase 5 applied to `Mock*` providers —
structurally correct, functionally a stand-in.

## 3. Bucket scheme

A generic, simplified grouping by mouth shape (the kind of classification
described in any general animation reference on lip sync), not any single
vendor's or product's proprietary viseme set:

| Shape | Sounds (approx.) | Mouth |
|---|---|---|
| REST | (pause) | Nearly closed |
| AI | a, i | Wide, open |
| E | e | Wide, slightly open |
| OH | o | Round, open |
| U | u | Small, rounded |
| WQ | w, q | Small, puckered |
| FV | f, v | Narrow, teeth-on-lip |
| MBP | m, b, p | Fully closed |
| L | l | Open, tongue-tip |
| ETC | everything else | Generic mid-open |

## 4. Timing

`chars_per_minute` (default 900) sizes a per-letter-run "unit" duration,
clamped to 60-140ms so no frame is imperceptibly short or unnaturally
long. Word boundaries always insert a 70ms `REST` frame, whether or not
the adjacent words happen to end/start in the same bucket — a spoken
pause is real regardless of the surrounding shapes.

## 5. Where it's computed and consumed

Computed once, in `VoiceConversationManager._log_turn`, from the *real*
(non-redacted) response text — visemes never leave the local-api process,
so redaction (which exists for logs/transcripts/events meant for storage)
doesn't apply to them. Published as part of the `voice.ui_state.changed`
(`SPEAKING`) event payload. Consumed entirely client-side by
`apps/desktop/src/avatar/Avatar.tsx`, which walks the timeline via
`requestAnimationFrame` against `speakingStartedAt` and reads the
currently-active frame with `activeVisemeAt`.

## 6. Verified

`tests/unit/test_voice_visemes.py` (11 tests): empty/whitespace/
punctuation-only text yields no frames; determinism; frame contiguity
(no gaps or overlaps); positive durations; word-boundary rests;
consecutive-same-bucket merging; every bucket reachable; speaking-rate
scaling changes duration but not the shape sequence.
`tests/integration/test_avatar_ui_state.py::
test_speaking_state_carries_a_real_viseme_timeline` confirms a real voice
turn's spoken response produces a non-empty, well-formed timeline
end-to-end.
