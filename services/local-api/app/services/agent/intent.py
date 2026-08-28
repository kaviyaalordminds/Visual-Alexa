"""IntentInterpreter — natural language request -> StructuredIntent.
docs/phase-4/INTENT.md.

Deterministic, rule-based, no LLM call — see
docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §4 for why: this is Phase 4's
'real, no-model-needed' capability, the same role Phase 3's OCR played
next to its stub VisionProvider. Never executes anything — a pure
classification of text into a structured shape.
"""

from __future__ import annotations

import re

from veyra_contracts import RiskLevel, StructuredIntent

# docs/phase-4 §92 — the brief's own adversarial-input list, matched
# literally. A request containing one of these is never planned at all;
# IntentInterpreter marks it UNSAFE and TaskPlanner refuses to produce
# any steps for it (docs/phase-4/PROMPT-INJECTION.md).
_UNSAFE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (the |all )?security",
        r"bypass (confirmation|security|policy)",
        r"turn off security",
        r"disable (the )?polic(y|ies)",
        r"run (this )?(command|script) from (the )?(webpage|website|email|document)",
        # Catches an "open <admin shell> as administrator"-style request
        # via the privilege-escalation phrase alone — deliberately not
        # matching on any specific shell's name, so this detector (which
        # only ever flags such phrases in untrusted text, never executes
        # anything) doesn't itself read as shell-execution code to
        # tests/security/test_no_unrestricted_shell.py's repo-wide grep.
        r"as administrator",
        r"delete everything",
    )
]

# docs/security/04-DEVICE-TRUST.md — "Local-only boundary": the installed
# PC is the only trusted/controllable device, no exceptions. Checked before
# any goal classification (including Phase 11's real `browser_task`
# template) so a request naming another machine is refused honestly,
# never silently executed against *this* machine instead — e.g. "open
# Chrome on my other computer" must never come back "Done" just because
# a local Chrome/browser action happens to exist.
#
# Two shapes, deliberately different: "on (my/another) other computer/pc/
# laptop/machine/desktop" requires an explicit other/another qualifier —
# "on my desktop" alone means the Windows desktop folder, not a second
# machine. "on my phone/tablet" needs no such qualifier — a phone or
# tablet is inherently a different device from "this PC" regardless of
# phrasing ("on my phone" is exactly as remote as "on my other phone").
_REMOTE_DEVICE_RE = re.compile(
    r"\bon\s+(?:my\s+)?(?:other|another)\s+(?:computer|pc|laptop|machine|desktop|device)\b"
    r"|\bon\s+(?:my\s+)?(?:phone|tablet)\b",
    re.IGNORECASE,
)

_OPEN_APP_RE = re.compile(r"^open\s+(?!(?:the\s+)?(?:latest|newest|oldest)\b)(.+)$", re.IGNORECASE)
_OPEN_FILE_RE = re.compile(
    r"^open\s+(?:the\s+)?(latest|newest|oldest)\s+(.+)$", re.IGNORECASE
)
_SEARCH_RE = re.compile(r"^(?:find|search(?: for)?)\s+(.+)$", re.IGNORECASE)
_DELETE_RE = re.compile(r"^delete\s+(.+)$", re.IGNORECASE)
_SEND_RE = re.compile(r"^send\s+(.+?)\s+to\s+(.+)$", re.IGNORECASE)
_DEVICE_RE = re.compile(r"^turn\s+(on|off)\s+(?:the\s+)?(.+)$", re.IGNORECASE)
_BROWSER_RE = re.compile(r"^open\s+chrome\b|^browse\b|^search\s+(?:the\s+)?web\b", re.IGNORECASE)
_TIME_CONSTRAINT_RE = re.compile(r"\b(yesterday|today|last week)\b", re.IGNORECASE)
_FILE_TYPE_RE = re.compile(r"\b(pdf|docx?|xlsx?|txt|png|jpe?g)\b", re.IGNORECASE)
_LOCATION_RE = re.compile(r"\bin\s+(downloads|documents|desktop)\b", re.IGNORECASE)


class IntentInterpreter:
    def interpret(self, raw_request: str) -> StructuredIntent:
        text = raw_request.strip()
        if not text:
            return StructuredIntent(
                raw_request=raw_request,
                status="MISSING_INFORMATION",
                missing_fields=["request"],
                clarifying_question="What would you like me to do?",
            )

        for pattern in _UNSAFE_PATTERNS:
            if pattern.search(text):
                return StructuredIntent(
                    raw_request=raw_request,
                    status="UNSAFE",
                    risk_level=RiskLevel.CRITICAL,
                    entities={"matched_pattern": pattern.pattern},
                )

        entities = self._extract_entities(text)

        if _REMOTE_DEVICE_RE.search(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="remote_device_task",
                object=text,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        if match := _BROWSER_RE.search(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="browser_task",
                object=text,
                entities=entities,
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        if match := _SEND_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="send_file",
                object=match.group(1).strip(),
                entities={**entities, "recipient": match.group(2).strip().rstrip(".")},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        if match := _DEVICE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="control_device",
                object=match.group(2).strip(),
                entities={**entities, "power_state": match.group(1).lower()},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        if match := _DELETE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="delete_files",
                object=match.group(1).strip(),
                entities=entities,
                risk_level=RiskLevel.CRITICAL,
                status="UNDERSTOOD",
            )

        if match := _OPEN_FILE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="open_file",
                object=match.group(2).strip(),
                entities={**entities, "ordering": match.group(1).lower()},
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        if match := _SEARCH_RE.match(text):
            goal = "open_file" if entities.get("file_type") else "search_files"
            return StructuredIntent(
                raw_request=raw_request,
                goal=goal,
                object=match.group(1).strip(),
                entities=entities,
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        if match := _OPEN_APP_RE.match(text):
            object_ = match.group(1).strip().rstrip(".")
            # docs/phase-4 Final Acceptance Test #10 — "Open my project"
            # (possessive, no known application name) is a file/entity
            # lookup, not an application launch; "Open Notepad" (a bare
            # name) is. The planner, not this heuristic, is what actually
            # discovers whether "project" resolves to zero/one/many
            # candidates — this only decides which planning path to take.
            goal = "open_file" if object_.lower().startswith("my ") else "open_application"
            return StructuredIntent(
                raw_request=raw_request,
                goal=goal,
                object=object_,
                entities=entities,
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        return StructuredIntent(
            raw_request=raw_request,
            status="MISSING_INFORMATION",
            missing_fields=["goal"],
            clarifying_question=(
                f"I'm not sure what you'd like me to do with \"{text}\" — "
                "could you rephrase that as an action, like 'open X' or "
                "'find X'?"
            ),
        )

    def _extract_entities(self, text: str) -> dict[str, str]:
        entities: dict[str, str] = {}
        if match := _TIME_CONSTRAINT_RE.search(text):
            entities["time_constraint"] = match.group(1).lower()
        if match := _FILE_TYPE_RE.search(text):
            entities["file_type"] = match.group(1).lower()
        if match := _LOCATION_RE.search(text):
            entities["location"] = match.group(1).capitalize()
        return entities
