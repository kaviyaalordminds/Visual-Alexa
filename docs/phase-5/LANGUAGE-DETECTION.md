# Language Detection

## 1. What it is

`detect_language(text: str) -> LanguageDetectionResult`
(`voice/core/language.py`) — a pure heuristic, not a model. Two signals:

1. **Tamil Unicode script ratio** (block U+0B80-U+0BFF) over all
   alphabetic characters — if it dominates (≥50%), the text is `TA`.
2. **Romanized-Tamil keyword dictionary** — ~45 common spoken-command
   words (`pannu`, `panni`, `irukka`, `la`, `venum`, `po`, `vaa`, ...) —
   any hit alongside ordinary Latin words means `TA_EN` (Tanglish).

Plain Latin text with neither signal is `EN`; no alphabetic content at all
is `UNKNOWN`.

## 2. Why a heuristic, not a model

`docs/architecture/08-VOICE.md` §2 already flagged general Tanglish
detection as an "unverified, industry-wide open problem"
(`docs/research/04-TECHNICAL-LIMITATIONS.md`). This heuristic is
deliberately narrow — VEYRA's own command vocabulary, not general text —
and its accuracy is only what's actually measured below, never claimed
beyond that (brief's own "do not claim language accuracy without actual
testing").

## 3. What was actually tested

The brief's own four worked examples, verbatim
(`tests/unit/test_voice_language.py`):

| Input | Detected | Expected |
|---|---|---|
| `Open Chrome.` | `EN` | `EN` |
| `Chrome open pannu.` | `TA_EN` | `TA_EN` |
| `Chrome open panni YouTube la AR Rahman song search pannu.` | `TA_EN` | `TA_EN` |
| `Veyra, Downloads folder la latest PDF open pannu.` | `TA_EN` | `TA_EN` |

All four pass. A native-script Tamil sentence (`க்ரோம் திற`) is also
covered and detects `TA`.

## 4. Known limitations

- The romanized-Tamil keyword list is not exhaustive — a Tanglish
  sentence using none of its ~45 words falls back to `EN`. Documented gap,
  see `TANGLISH.md` §3.
- No confidence calibration against a real speech corpus — `confidence`
  values are heuristic proportions (keyword-hit ratio, script ratio), not
  measured accuracy.
- `la` is included as a Tanglish marker word; a genuine false positive is
  possible on an English sentence that happens to contain the standalone
  word "la" (e.g. "LA" as a place name) — accepted trade-off, documented
  here rather than silently risked.
