# Plugin Architecture

## 1. Default deny, always

Brief §63/§65: "do not treat every plugin as trusted"; "Default: DENY."
`PluginRegistry.install(session, manifest)` always lands a plugin in
`UNTRUSTED` with **zero** granted permissions, regardless of what its
own manifest requests. A plugin's manifest is the *ceiling* of what it
can ever be granted, never the floor:

- `grant(plugin_id, permission)` refuses any permission the manifest
  didn't itself request (`PermissionNotRequestedError`) — there is
  nothing a caller can grant beyond what was declared up front.
- `enable(session, tool_registry, plugin_id)` only ever registers a tool
  into the real `ToolRegistry` when that tool's `required_permission` is
  one of the plugin's *currently-granted* permissions. A tool whose
  permission was requested but never granted (or granted then revoked)
  simply never goes live — denial by omission, the same shape
  `ToolRegistry.disable()` already uses for ordinary tools.

## 2. States

`UNTRUSTED -> [REVIEW_REQUIRED] -> TRUSTED -> ENABLED/DISABLED ->
REVOKED` (brief §63). `mark_trusted` is the one extension point a real
review process would call — this skeleton makes no automated trust
decision of its own. `enable` requires `TRUSTED` or `DISABLED` (a
previously-enabled plugin can be re-enabled without re-review);
`REVIEW_REQUIRED`/`REVOKED` are real enum members with no automated
producer in this phase (no review pipeline exists yet to move a plugin
into/out of them).

## 3. Never executing plugin code

Brief §69: "Never execute plugin code directly from... a downloaded
file without validation." `PluginRegistry.install`'s `tool_builder`
parameter (a callable that returns the plugin's actual tool
definitions + executors) can therefore only ever come from a
server-side Python call — `POST /plugins/install`
(`app/api/plugins.py`) always installs with **no** builder at all,
meaning an HTTP-installed plugin is metadata/permissions only, tracked
and grantable, but structurally incapable of ever registering a live
tool. No manifest field, however crafted, can smuggle a `tool_builder`
through the HTTP layer — `tests/security/test_phase7_platform_security.py::
test_plugin_install_endpoint_cannot_smuggle_a_tool_builder` proves a
manifest naming `filesystem.delete_everything` in its `tools` list never
causes that id to appear in `GET /tools`.

## 4. `remove`

Brief §67: "disable tools, revoke credentials, remove registrations,
clear temporary resources." `remove()` unregisters every tool the
plugin had live, then hard-deletes its `PluginPermission` rows and its
own `Plugin` row — full teardown, not a soft-revoke.

## 5. Acceptance test (brief §170)

A mock plugin manifest requesting `filesystem.read` + `network.access`
(and declaring two prospective tools, one needing `filesystem.read`, one
needing `filesystem.write` — a permission the manifest never requests
at all): granting `filesystem.write` is rejected outright
(`PermissionNotRequestedError`); after granting only `filesystem.read`,
trusting, and enabling, the `filesystem.read` tool is live and the
`filesystem.write` tool never appears in the registry — proven both in
isolation (`tests/unit/test_plugin_registry.py`) and through the real
HTTP API (`tests/integration/test_plugins_api.py`).

## 6. What's not delivered

No real plugin execution/sandboxing (brief §64) — nothing in this phase
ever imports or runs a plugin's actual code, so there is no sandbox to
build yet. No plugin marketplace/discovery UI (brief §66) beyond the
read-only list in the desktop shell's Platform panel. No dependency
resolution for `PluginManifest.dependencies` — tracked, never enforced.
