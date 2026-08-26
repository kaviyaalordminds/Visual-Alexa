# Filesystem Control

The most safety-critical part of Phase 2, and the part most fully
verified in this environment — every claim below is backed by a real test
against a real filesystem (`tests/unit/test_filesystem_engine.py`,
`tests/unit/test_path_policy.py`, `tests/integration/test_filesystem_tools_api.py`,
`tests/security/test_phase2_path_security_api.py`).

## Path security (`computer_control.filesystem.path_policy`)

Every path any `filesystem.*` tool touches goes through
`PathValidator.validate()` before any real filesystem call:

1. **UNC/device/protocol paths rejected outright** — `\\server\share`,
   `//server/share`, `\\.\PhysicalDrive0`, `\\?\...`, and any
   `scheme://...` string never reach step 2 at all
   (`_UNC_OR_DEVICE_PATH` / `_PROTOCOL_PATH` regexes).
2. **Resolved and checked against protected patterns.** `WINDOWS_PROTECTED_PATTERNS`
   (System32, Program Files, ProgramData, the Recycle Bin, System Volume
   Information) and `POSIX_PROTECTED_PATTERNS` (`/etc`, `/bin`, `/usr`,
   `/boot`, `/sys`, `/proc`, `/root`, `/dev`, ...) are checked *before*
   the allowed-roots check — a protected path is denied even if it
   happens to fall under a configured allowed root.
3. **Checked against `AllowedRoots`.** The path must resolve to be equal
   to, or a descendant of, at least one configured root; anything else is
   `PATH_NOT_ALLOWED`. There is no allow-all default —
   `PathPolicy.__post_init__` raises if `allowed_roots` is empty.

`AllowedRoots` are resolved per-deployment by
`app/services/filesystem_config.py`: on Windows, the user's
Documents/Downloads/Desktop; elsewhere (this development container),
`~/veyra_workspace`, falling back to `/tmp/veyra_workspace` when `$HOME`
itself is a protected path (true in this root-run container — documented
in `filesystem_config.py` rather than silently widening the protected-path
allowlist to work around it).

Path traversal is defeated by resolving the path (`Path.resolve()`,
which normalizes `..` segments) before any check runs, not by
string-matching `".."` — verified directly:
`test_traversal_outside_allowed_root_is_denied` constructs
`<sandbox>/../../etc/passwd` and confirms it's denied (as `PATH_PROTECTED`,
since `/etc` is also a protected pattern — both denial reasons are
individually tested).

## FilesystemEngine — no delete method exists

`computer_control.filesystem.engine.FilesystemEngine` implements `search`,
`list_directory`, `get_metadata`, `open_file`, `create_folder`,
`create_file`, `copy`, `move`, `rename`. There is no `delete` method on the
class at all — `test_no_delete_method_exists_on_the_engine` asserts
`hasattr(FilesystemEngine, "delete") is False`. This is stronger than "no
delete tool is registered": even a future bug in tool registration could
not accidentally wire up deletion, because the capability doesn't exist in
the engine to wire up.

## Search is bounded, not "search the whole disk"

`filesystem.search` always requires a `directory` (which itself must
validate against the allowed roots) and defaults `max_results=200` —
verified by `test_search_is_bounded_by_max_results`. There is no
"search everywhere" mode.

## `filesystem.open`

Resolves the path, confirms it exists, then calls a platform-appropriate
launcher (`computer_control.launcher.default_launcher()`): `os.startfile`
on Windows, `xdg-open`/`open` via a reviewed list-argv subprocess call
elsewhere. Per docs/phase-2 §21, the tool honestly reports `EXECUTED`, not
`VERIFIED` — there is no reliable cross-application way to confirm the
associated viewer actually opened a window, and the code says so in its
own `VerificationOutcome.detail` rather than fabricating a passing
verification.

## Risk tiers

`search`, `list_directory`, `get_metadata`, `open` are SAFE (matches the
brief's own "search files"/"open application" SAFE examples).
`create_folder`, `create_file`, `copy`, `move`, `rename` are MODERATE
(matches the brief's own "create folder, rename file, move file" MODERATE
examples exactly).
