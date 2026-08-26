# Human-in-the-Loop

Brief §57-59: some situations (CAPTCHA, 2FA, OTP, unexpected security
warnings, permission dialogs, unknown application prompts) cannot safely
be automated. VEYRA stops and asks.

## 1. State machine support

`TaskState.EXECUTING → WAITING_USER` is an additive Phase 4 transition
(see `TASK-STATE-MACHINE.md` §3) specifically for this case — distinct
from `WAITING_PERMISSION` (a Policy Engine confirmation gate) and from
the ambiguity-driven `WAITING_USER` reached from `PLANNING`/`UNDERSTANDING`.
`WAITING_USER → EXECUTING` lets a task resume the *same* plan directly
once the human has completed whatever it was waiting on (brief §58's
"...USER COMPLETES AUTHENTICATION → VEYRA RESUMES"), never a full
replan.

## 2. Not automated in Phase 4

No tool or orchestrator logic in this phase actually *detects* a CAPTCHA,
2FA prompt, or unknown application dialog — that detection would require
either a registered browser-automation capability (not built — brief §64,
interfaces only) or Phase 3 vision/OCR results being fed into the
orchestrator's decision loop (not built — see `PROMPT-INJECTION.md` §1).
What Phase 4 delivers is the *state machine support and pause/resume
mechanism* such detection would plug into — the human-in-the-loop pause
itself is exercised today only via the same generic `WAITING_USER`/
`resume_after_confirmation` machinery the confirmation flow uses,
verified in `tests/integration/test_agent_tasks_api.py`.

## 3. Never attempts to bypass

There is no code anywhere in this codebase that submits a CAPTCHA
solution, extracts a credential, or clicks through a security warning
programmatically — no such capability exists, matching brief §57's "must
never attempt to bypass CAPTCHA or security controls" and CLAUDE.md's
absolute security rules by simple absence.

## 4. Authentication barriers (brief §58)

Same absence-based guarantee: no tool in Phase 1-4 reads or stores a
password/OTP/2FA code on the user's behalf. If a step's target turns out
to be a password field (Phase 3's `PrivacyLevel.SECRET` classification,
`docs/phase-3/PRIVACY.md`), nothing in the orchestrator has any mechanism
to fill it — the closest it comes is planning a `filesystem.open` or
`application.launch` call, neither of which touches form fields at all.
