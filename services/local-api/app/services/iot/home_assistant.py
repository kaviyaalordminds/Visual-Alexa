"""Home Assistant REST API client — thin, stateless wrapper over HA's
documented REST API. Only speaks to the URL/token the operator configured;
never guesses device names or entity IDs — the caller supplies them from
a StructuredIntent that was itself validated before reaching here.

CLAUDE.md: no unrestricted shell/exec, no hardcoded secrets. The HA token
is loaded from settings (environment variable VEYRA_HA_TOKEN), never
stored in plaintext in the DB, and never returned by any endpoint.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0

# Common domain/service mappings for natural-language device names.
# These are conservative — only well-understood HA domains. An unknown
# device falls back to a raw entity_id the caller must supply.
_DOMAIN_ALIASES: dict[str, str] = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "ac": "climate",
    "air conditioning": "climate",
    "thermostat": "climate",
    "heater": "climate",
    "fan": "fan",
    "tv": "media_player",
    "television": "media_player",
    "switch": "switch",
    "plug": "switch",
    "cover": "cover",
    "blind": "cover",
    "blinds": "cover",
    "curtain": "cover",
    "curtains": "cover",
    "lock": "lock",
    "door": "lock",
}


class HomeAssistantClient:
    """Calls Home Assistant's REST API. Stateless: constructed fresh per
    call (no session pool needed for occasional IoT requests)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ha_base_url.rstrip("/")
        self._token = settings.ha_token

    def is_configured(self) -> bool:
        return bool(self._base_url and self._token)

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str | None = None,
        extra: dict | None = None,
    ) -> dict:
        """POST /api/services/{domain}/{service}.
        Returns HA's JSON response or raises HomeAssistantError."""
        if not self.is_configured():
            raise HomeAssistantError("Home Assistant is not configured.")
        url = f"{self._base_url}/api/services/{domain}/{service}"
        payload: dict = {}
        if entity_id:
            payload["entity_id"] = entity_id
        if extra:
            payload.update(extra)
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code in (200, 201):
                try:
                    return response.json()
                except Exception:
                    return {"ok": True}
            raise HomeAssistantError(
                f"Home Assistant returned HTTP {response.status_code}."
            )
        except httpx.TimeoutException:
            raise HomeAssistantError(
                f"Home Assistant did not respond within {_TIMEOUT:.0f}s."
            )
        except httpx.HTTPError as exc:
            raise HomeAssistantError(f"Home Assistant unreachable: {exc.__class__.__name__}.")

    async def get_state(self, entity_id: str) -> dict:
        """GET /api/states/{entity_id}."""
        if not self.is_configured():
            raise HomeAssistantError("Home Assistant is not configured.")
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
            if response.status_code == 200:
                return response.json()
            raise HomeAssistantError(
                f"Home Assistant returned HTTP {response.status_code} for state query."
            )
        except httpx.TimeoutException:
            raise HomeAssistantError(
                f"Home Assistant did not respond within {_TIMEOUT:.0f}s."
            )
        except httpx.HTTPError as exc:
            raise HomeAssistantError(f"Home Assistant unreachable: {exc.__class__.__name__}.")


class HomeAssistantError(Exception):
    pass


def resolve_domain(device_name: str) -> str:
    """Best-effort domain resolution from a human-readable device name.
    Falls back to 'homeassistant' (the HA universal domain) if unknown."""
    key = device_name.strip().lower()
    return _DOMAIN_ALIASES.get(key, "homeassistant")


def device_name_to_entity_id(device_name: str, domain: str) -> str:
    """Convert 'Living Room Light' → 'light.living_room_light'.
    This is a heuristic — a real deployment would let the user configure
    entity IDs via VEYRA's Memory/integration settings."""
    slug = device_name.strip().lower()
    slug = slug.replace(" ", "_").replace("-", "_")
    import re
    slug = re.sub(r"[^\w]", "", slug)
    return f"{domain}.{slug}"
