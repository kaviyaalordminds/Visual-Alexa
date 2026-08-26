# Performance

Measured, not fabricated — captured in this environment (container CPU,
`Xvfb` virtual display at 1280×800), 2026-08-26.

## 1. Real measurements

| Stage | Input | Time |
|---|---|---|
| OCR extract (`OCREngine.extract`) | 300×80 rendered PNG, one word | 115.4 ms |
| Full screen capture (`MssScreenBackend.capture_full`) | 1280×800 virtual display | 68.7 ms |
| Perception fusion (`PerceptionFusion.fuse`) | 3-5 candidate elements | sub-millisecond (pure Python, no I/O) |
| Grounding (`GroundingEngine.ground`) | 3-5 candidates | sub-millisecond |
| Scene diff (`compute_scene_diff`) | small trees (<10 nodes) | sub-millisecond |

OCR dominates observation latency by roughly an order of magnitude over
fusion/grounding/diff, which matches the priority-order design: UIA (no
OCR needed) answers most questions without paying this cost at all.
Container-relative numbers, not representative of real Windows hardware
(no GPU acceleration path is used by tesseract here); recorded as a
baseline, not a target.

## 2. Why vision is skipped by default

`ObservationCoordinator.observe`'s `include_vision` defaults to `False`,
and `ground_target`'s `decide_next_tier` only reaches the vision tier
after both UIA and OCR report `NOT_FOUND` — with only
`NotConfiguredVisionProvider` shipped, that call is a no-op anyway, but
the short-circuit means a *future* real provider's latency is never paid
unnecessarily either.

## 3. No unlimited history

`vision.core.cache.ObservationCache` bounds both dimensions the brief
warns about: `ttl_seconds` (default 60s) expires entries even if never
read, and `max_entries` (default 20) evicts the oldest entry once the cap
is hit — verified in `tests/unit/test_vision_cache.py` (expiry and
eviction both exercised with real `time.sleep`, not mocked clocks).

## 4. Event-driven, not polling

No tool in this phase runs on a timer or loop by itself — `screen.observe`,
`ocr.extract`, etc. are all one-shot, caller-triggered calls. The visual
wait conditions (`vision/core/waiting.py`) poll only when a caller
explicitly asks to wait for a condition, with an explicit
`poll_interval_seconds` and `timeout_seconds`, and are naturally
cancellable (`asyncio.CancelledError` via the loop's only suspension
point, `asyncio.sleep` — same discipline as
`computer_control.core.waiting.wait_for_element`). There is no
continuous/high-frequency screenshot loop anywhere in this codebase.
