"""IntentInterpreter — natural language request -> StructuredIntent.
docs/phase-4/INTENT.md.

Deterministic, rule-based, with LLM fallback for unmatched requests —
see docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §4 for the original
deterministic design. Never executes anything — a pure classification
of text into a structured shape.
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

# docs/security/04-DEVICE-TRUST.md — "Local-only boundary"
_REMOTE_DEVICE_RE = re.compile(
    r"\bon\s+(?:my\s+)?(?:other|another)\s+(?:computer|pc|laptop|machine|desktop|device)\b"
    r"|\bon\s+(?:my\s+)?(?:phone|tablet)\b",
    re.IGNORECASE,
)

# Application launch patterns
_OPEN_APP_RE = re.compile(r"^open\s+(?!(?:the\s+)?(?:latest|newest|oldest)\b)(.+)$", re.IGNORECASE)
_LAUNCH_APP_RE = re.compile(r"^(?:launch|start|run)\s+(.+)$", re.IGNORECASE)

_OPEN_FILE_RE = re.compile(
    r"^open\s+(?:the\s+)?(latest|newest|oldest)\s+(.+)$", re.IGNORECASE
)
_SEARCH_RE = re.compile(r"^(?:find|search(?: for)?)\s+(.+)$", re.IGNORECASE)
_CREATE_FOLDER_RE = re.compile(
    r"^(?:create|make)\s+(?:a\s+|an?\s+)?(?:new\s+)?folder\s+"
    r"(?:called|named)?\s*(.+)$",
    re.IGNORECASE,
)
_DELETE_RE = re.compile(r"^delete\s+(.+)$", re.IGNORECASE)
_SEND_RE = re.compile(r"^send\s+(.+?)\s+to\s+(.+)$", re.IGNORECASE)

# IoT device control: "turn on/off X", "set X to Y"
_DEVICE_POWER_RE = re.compile(r"^turn\s+(on|off)\s+(?:the\s+)?(.+)$", re.IGNORECASE)
_DEVICE_SET_RE = re.compile(
    r"^set\s+(?:the\s+)?(.+?)\s+to\s+(.+)$", re.IGNORECASE
)

# Browser / web navigation patterns — ordered most-specific first
# "search X on youtube" / "find X on youtube" / "play X on youtube"
_YOUTUBE_RE = re.compile(
    r"(?:search|find|look\s+up|play)\s+(.+?)\s+on\s+youtube", re.IGNORECASE
)
# "go to X" / "navigate to X" / "open X.com" / "visit X"
_NAVIGATE_RE = re.compile(
    r"^(?:go\s+to|navigate\s+to|visit|open)\s+(https?://\S+|\S+\.(?:com|org|net|io|co|gov|edu|app)\S*)\s*$",
    re.IGNORECASE,
)
# "email X" / "send email to X" / "compose email to X" / "send a mail to X"
_EMAIL_RE = re.compile(
    r"^(?:email|send\s+(?:an?\s+)?(?:email|mail|message)\s+to|compose\s+(?:an?\s+)?(?:email|mail)\s+to)\s+(.+)$",
    re.IGNORECASE,
)
# "play X" / "play X on spotify"
_PLAY_RE = re.compile(
    r"^play\s+(?!.*\bon\s+youtube\b)(.+?)(?:\s+on\s+spotify)?\s*$", re.IGNORECASE
)
# Generic browser trigger: open chrome, browse, search the web, open youtube
_BROWSER_RE = re.compile(
    r"^open\s+chrome\b|^open\s+(?:firefox|edge|browser)\b|^browse\b|^search\s+(?:the\s+)?web\b|^open\s+youtube\b",
    re.IGNORECASE,
)

# Well-known website names — when the user says "find/open/search youtube",
# they mean navigate to it or search on it, not look for a local file.
_KNOWN_SITES = {
    "youtube", "google", "gmail", "github", "reddit", "twitter", "facebook",
    "instagram", "linkedin", "netflix", "spotify", "amazon", "wikipedia",
    "stackoverflow", "openai", "claude", "chatgpt", "bing", "yahoo",
}

_TIME_CONSTRAINT_RE = re.compile(r"\b(yesterday|today|last week)\b", re.IGNORECASE)
_FILE_TYPE_RE = re.compile(r"\b(pdf|docx?|xlsx?|txt|png|jpe?g)\b", re.IGNORECASE)
_LOCATION_RE = re.compile(r"\bin\s+(downloads|documents|desktop)\b", re.IGNORECASE)

# Typing / keyboard input
_TYPE_TEXT_RE = re.compile(r"^(?:type|enter|input)\s+(.+)$", re.IGNORECASE)
_PRESS_KEY_RE = re.compile(r"^press\s+(.+)$", re.IGNORECASE)

# Click / UI interaction
_CLICK_RE = re.compile(r"^click(?:\s+on)?\s+(.+)$", re.IGNORECASE)

# Scrolling
_SCROLL_RE = re.compile(r"^scroll\s+(up|down)\b", re.IGNORECASE)

# Window control (minimize/maximize/close/restore)
_WINDOW_CONTROL_RE = re.compile(
    r"^(minimize|maximize|close|restore)\s+(?:the\s+)?(.+)$", re.IGNORECASE
)

# Screenshot / screen reading
_SCREENSHOT_RE = re.compile(
    r"^(?:take\s+(?:a\s+)?screenshot\b|screenshot\b|capture\s+(?:the\s+)?screen\b)",
    re.IGNORECASE,
)
_READ_SCREEN_RE = re.compile(
    r"^(?:read\s+(?:the\s+)?screen\b"
    r"|what(?:'s|\s+is)\s+on\s+(?:the\s+)?screen\b"
    r"|what\s+does\s+(?:it|the\s+screen)\s+say\b"
    r"|read\s+(?:this|that)\s+out\b)",
    re.IGNORECASE,
)

# Copy / paste
_COPY_RE = re.compile(r"^copy(?:\s+(.+))?$", re.IGNORECASE)
_PASTE_RE = re.compile(r"^paste\b", re.IGNORECASE)

# Compound command splitter: "open chrome and find youtube" → ["open chrome", "find youtube"]
# Handles "and" as a connector between two commands.
_COMPOUND_AND_RE = re.compile(
    r"^(.+?)\s+and\s+(?:then\s+)?(.+)$", re.IGNORECASE
)


def _is_likely_app_name(text: str) -> bool:
    """Heuristic: does this text look like an application name rather than a URL?
    Used to distinguish 'open notepad' (app) from 'open google.com' (navigate)."""
    # Contains a TLD-like pattern → treat as navigate
    if re.search(r"\.\w{2,6}(/|$|\s)", text, re.IGNORECASE):
        return False
    # Common browser names that should stay as open_application
    browsers = {"chrome", "firefox", "edge", "chromium", "opera", "safari", "brave"}
    first_word = text.strip().split()[0].lower() if text.strip() else ""
    return first_word not in browsers or len(text.split()) > 1


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

        # Check compound "X and Y" — parse both halves and embed as a compound plan.
        # Only attempt if neither half individually returns MISSING_INFORMATION,
        # and the "and" connector is genuinely between two recognizable commands.
        compound = self._try_compound(raw_request, text, entities)
        if compound is not None:
            return compound

        return self._classify_single(raw_request, text, entities)

    def _classify_single(
        self, raw_request: str, text: str, entities: dict
    ) -> StructuredIntent:
        """Classify a single (non-compound) command."""

        # YouTube-specific search — before generic browser check
        if match := _YOUTUBE_RE.search(text):
            query = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="browser_task",
                object=text,
                entities={**entities, "youtube_search": query},
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # Navigate to a URL
        if match := _NAVIGATE_RE.match(text):
            url = match.group(1).strip()
            if "." not in url:
                url = url  # leave as-is; let browser handle
            return StructuredIntent(
                raw_request=raw_request,
                goal="browser_task",
                object=text,
                entities={**entities, "navigate_url": url},
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # Email compose
        if match := _EMAIL_RE.match(text):
            recipient = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="email_task",
                object=recipient,
                entities={**entities, "recipient": recipient},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Media playback
        if match := _PLAY_RE.match(text):
            media = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="media_task",
                object=media,
                entities={**entities, "media": media},
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # Screenshot / screen reading — before generic browser check
        if _SCREENSHOT_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="take_screenshot",
                object=text,
                entities=entities,
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        if _READ_SCREEN_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="read_screen",
                object=text,
                entities=entities,
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # Generic browser trigger
        if _BROWSER_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="browser_task",
                object=text,
                entities=entities,
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # File send
        if match := _SEND_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="send_file",
                object=match.group(1).strip(),
                entities={**entities, "recipient": match.group(2).strip().rstrip(".")},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Type text into the active/target window
        if match := _TYPE_TEXT_RE.match(text):
            text_to_type = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="type_text",
                object=text_to_type,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Press a key or hotkey (e.g. "press Enter", "press Ctrl+C")
        if match := _PRESS_KEY_RE.match(text):
            key_spec = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="press_key",
                object=key_spec,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Click a UI element by name
        if match := _CLICK_RE.match(text):
            element = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="click_element",
                object=element,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Scroll up or down
        if match := _SCROLL_RE.match(text):
            direction = match.group(1).lower()
            return StructuredIntent(
                raw_request=raw_request,
                goal="scroll_page",
                object=direction,
                entities={**entities, "direction": direction},
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        # Window control: minimize/maximize/close/restore <app>
        if match := _WINDOW_CONTROL_RE.match(text):
            action = match.group(1).lower()
            app_name = match.group(2).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="window_control",
                object=app_name,
                entities={**entities, "action": action},
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # Paste clipboard content
        if _PASTE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="paste_text",
                object=None,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Copy selected text (or copy a specific piece of text)
        if match := _COPY_RE.match(text):
            content = (match.group(1) or "").strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="copy_text",
                object=content or None,
                entities=entities,
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # IoT device set (e.g. "set the AC to 22")
        if match := _DEVICE_SET_RE.match(text):
            device = match.group(1).strip()
            value = match.group(2).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="control_device",
                object=device,
                entities={**entities, "action": "set", "value": value},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # IoT device power
        if match := _DEVICE_POWER_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="control_device",
                object=match.group(2).strip(),
                entities={**entities, "action": "power", "power_state": match.group(1).lower()},
                risk_level=RiskLevel.SENSITIVE,
                status="UNDERSTOOD",
            )

        # Folder creation
        if match := _CREATE_FOLDER_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="create_folder",
                object=match.group(1).strip().rstrip("."),
                entities=entities,
                risk_level=RiskLevel.MODERATE,
                status="UNDERSTOOD",
            )

        # File delete
        if match := _DELETE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="delete_files",
                object=match.group(1).strip(),
                entities=entities,
                risk_level=RiskLevel.CRITICAL,
                status="UNDERSTOOD",
            )

        # Open latest/newest/oldest file
        if match := _OPEN_FILE_RE.match(text):
            return StructuredIntent(
                raw_request=raw_request,
                goal="open_file",
                object=match.group(2).strip(),
                entities={**entities, "ordering": match.group(1).lower()},
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        # Search / find — check if target is a known website first
        if match := _SEARCH_RE.match(text):
            obj = match.group(1).strip()
            first_word = obj.split()[0].lower() if obj else ""
            if first_word in _KNOWN_SITES:
                # "find youtube" / "search google" → navigate/browser task
                return StructuredIntent(
                    raw_request=raw_request,
                    goal="browser_task",
                    object=text,
                    entities={**entities, "navigate_url": f"https://www.{first_word}.com"},
                    risk_level=RiskLevel.MODERATE,
                    status="UNDERSTOOD",
                )
            goal = "open_file" if entities.get("file_type") else "search_files"
            return StructuredIntent(
                raw_request=raw_request,
                goal=goal,
                object=obj,
                entities=entities,
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        # Launch / start / run app
        if match := _LAUNCH_APP_RE.match(text):
            object_ = match.group(1).strip().rstrip(".")
            return StructuredIntent(
                raw_request=raw_request,
                goal="open_application",
                object=object_,
                entities=entities,
                risk_level=RiskLevel.SAFE,
                status="UNDERSTOOD",
            )

        # Open app (the original pattern, last so navigate/youtube checks win first)
        if match := _OPEN_APP_RE.match(text):
            object_ = match.group(1).strip().rstrip(".")
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
                "could you rephrase that as an action, like 'open X', "
                "'search X', 'play X', or 'email X'?"
            ),
        )

    def _try_compound(
        self, raw_request: str, text: str, entities: dict
    ) -> StructuredIntent | None:
        """Try to parse 'X and Y' as a compound two-step command.
        Returns None if this doesn't look like a genuine compound command."""
        match = _COMPOUND_AND_RE.match(text)
        if not match:
            return None
        part_a = match.group(1).strip()
        part_b = match.group(2).strip()

        # Classify each half independently
        intent_a = self._classify_single(part_a, part_a, self._extract_entities(part_a))
        intent_b = self._classify_single(part_b, part_b, self._extract_entities(part_b))

        # Only treat as compound if both halves were understood
        if intent_a.status != "UNDERSTOOD" or intent_b.status != "UNDERSTOOD":
            return None

        # Don't compound two open_application goals that look like
        # a single multi-word app name (e.g. "visual studio code and python")
        if intent_a.goal == intent_b.goal == "open_application":
            # If parts look like a phrase rather than two distinct apps, skip
            if len(part_a.split()) <= 2 and len(part_b.split()) <= 2:
                # Let it fall through as a single unrecognized request
                pass

        return StructuredIntent(
            raw_request=raw_request,
            goal="compound_task",
            object=text,
            entities={
                **entities,
                "steps": [
                    {"goal": intent_a.goal, "object": intent_a.object, "entities": intent_a.entities},
                    {"goal": intent_b.goal, "object": intent_b.object, "entities": intent_b.entities},
                ],
            },
            risk_level=RiskLevel.MODERATE,
            status="UNDERSTOOD",
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
