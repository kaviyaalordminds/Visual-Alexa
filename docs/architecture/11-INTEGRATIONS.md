# 11 — Integrations Architecture

## 1. Principle

Integrations are adapters at the edge of the system, never core-coupled.
Official APIs and OAuth only; no undocumented/reverse-engineered API usage.
Browser automation is used only where a service has no suitable official
API and only within the browser control architecture's DOM-first rules
(`06-BROWSER-CONTROL.md`) — never as a default first choice.

## 2. Interface

```
Integration (interface)
  id: str
  auth_method: AuthMethod        # OAUTH2 | API_KEY | NONE
  connect(credentials) -> ConnectionResult
  disconnect()
  capabilities: list[str]        # e.g. ["send_message", "read_inbox"]
  invoke(capability, args) -> IntegrationResult
```

Every `Integration` capability that performs an action is registered in the
Tool Registry like any other tool, with its own `risk_level` (e.g.,
`communication.send_email` is `SENSITIVE`) — integrations do not bypass the
Policy Engine.

## 3. Planned adapters (directories + interfaces only in Phase 1)

`integrations/email`, `integrations/whatsapp`, `integrations/media`,
`integrations/browser`, `integrations/iot`.

- **Email** (Gmail/Outlook): official OAuth2 APIs only.
- **WhatsApp**: explicitly excluded from Phase 1 per the brief §"Do not
  implement WhatsApp automation." When implemented in a future phase, must
  use WhatsApp's official Business Platform APIs — not browser-session
  automation of the consumer WhatsApp Web client — pending a dedicated
  security/ToS review.
- **Media** (YouTube/Spotify): official APIs (YouTube Data API, Spotify Web
  API) with OAuth where required.
- **Browser**: shares `06-BROWSER-CONTROL.md`'s architecture.
- **IoT**: shares `10-IOT.md`'s device gateway, not a separate model.

## 4. Phase 1 scope

Delivered: the `Integration` interface and directory structure. Not
delivered: any live integration — explicitly out of Phase 1 scope.
