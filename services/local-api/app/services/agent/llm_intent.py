"""LLM-backed intent fallback — called by AgentOrchestrator when the
deterministic IntentInterpreter returns MISSING_INFORMATION.

Sends a structured prompt to the configured LLM provider and parses
its JSON response into a StructuredIntent. Never raises — on any
failure (LLM not configured, timeout, parse error) returns None so
the orchestrator can fall back to asking the user.

CLAUDE.md: "No vendor-specific AI SDK may be imported outside its
designated provider adapter module." This module only calls
`build_llm_provider` which is already that adapter.
"""

from __future__ import annotations

import json
import logging

from veyra_contracts import RiskLevel, StructuredIntent

from app.core.config import get_settings
from app.services.agent.llm_provider import NotConfiguredLLMProvider
from app.services.agent.providers import build_llm_provider

logger = logging.getLogger(__name__)

_INTENT_GOALS = [
    "open_application",
    "search_files",
    "open_file",
    "create_folder",
    "delete_files",
    "browser_task",
    "email_task",
    "media_task",
    "control_device",
    "compound_task",
    "send_file",
]

_SYSTEM_PROMPT = """\
You are an intent classifier for VEYRA, a local AI assistant that controls a Windows PC.
Classify the user's request into a JSON object with these fields:
- goal: one of """ + ", ".join(f'"{g}"' for g in _INTENT_GOALS) + """
- object: the primary target (app name, file, device name, URL, person, etc.)
- entities: a JSON object with extra context. For browser_task include "navigate_url" or "youtube_search" or "web_search" key. For control_device include "action" ("power"/"set"), "power_state" ("on"/"off"), and/or "value". For compound_task include "steps" as an array of {goal, object, entities}.
- risk_level: "SAFE", "MODERATE", "SENSITIVE", or "CRITICAL"

Respond with ONLY a JSON object, no explanation, no markdown.
"""


async def llm_classify_intent(raw_request: str) -> StructuredIntent | None:
    """Returns a StructuredIntent if LLM classification succeeds, else None."""
    settings = get_settings()
    provider = build_llm_provider(settings)
    if isinstance(provider, NotConfiguredLLMProvider):
        return None

    prompt = f"User request: {raw_request}"
    try:
        result = await provider.understand(
            _SYSTEM_PROMPT + "\n\nNow classify:\n" + prompt
        )
        if not result.available or not result.content:
            return None
        data = _parse_json(result.content)
        if data is None:
            return None
        return _build_intent(raw_request, data)
    except Exception as exc:
        logger.warning("[LLM-INTENT] Classification failed: %s", exc)
        return None


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract a JSON block from the response
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _build_intent(raw_request: str, data: dict) -> StructuredIntent | None:
    goal = data.get("goal", "")
    if goal not in _INTENT_GOALS:
        return None
    risk_map = {
        "SAFE": RiskLevel.SAFE,
        "MODERATE": RiskLevel.MODERATE,
        "SENSITIVE": RiskLevel.SENSITIVE,
        "CRITICAL": RiskLevel.CRITICAL,
    }
    risk = risk_map.get(str(data.get("risk_level", "MODERATE")).upper(), RiskLevel.MODERATE)
    entities = data.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}
    return StructuredIntent(
        raw_request=raw_request,
        goal=goal,
        object=str(data.get("object", "")),
        entities=entities,
        risk_level=risk,
        status="UNDERSTOOD",
    )
