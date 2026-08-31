"""LLM-powered conversational fallback — generates a natural spoken
response when the deterministic intent interpreter and LLM intent
classifier both fail to find an actionable PC-control command.

CLAUDE.md: "No vendor-specific AI SDK may be imported outside its
designated provider adapter module." Uses `build_llm_provider`, the
same adapter `llm_intent.py` uses, with a VEYRA-persona system prompt.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.services.agent.llm_provider import NotConfiguredLLMProvider
from app.services.agent.providers import build_llm_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are VEYRA, a friendly and intelligent local AI assistant that controls a Windows PC. "
    "You can open applications, search the web, play media, control windows, type text, "
    "take screenshots, read the screen, and much more. "
    "When the user asks a general question or starts a conversation, respond helpfully and naturally "
    "in 1-2 sentences. Be warm, concise, and conversational. "
    "Never claim to have done something you haven't. "
    "If you cannot help with something, say so briefly and suggest what you can do instead."
)


async def llm_converse(user_utterance: str) -> str | None:
    """Generate a natural conversational response using the configured LLM.

    Returns the response string, or None if no LLM provider is configured
    or if the call fails — callers should fall back to a canned response.
    """
    settings = get_settings()
    provider = build_llm_provider(settings)
    if isinstance(provider, NotConfiguredLLMProvider):
        return None
    try:
        prompt = _SYSTEM_PROMPT + "\n\nUser: " + user_utterance + "\nVEYRA:"
        result = await provider.understand(prompt)
        if result.available and result.content:
            return result.content.strip()
    except Exception as exc:
        logger.warning("[LLM-CONVERSE] Conversational response failed: %s", exc)
    return None
