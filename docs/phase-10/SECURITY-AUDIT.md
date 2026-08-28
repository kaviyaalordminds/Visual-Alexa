# Phase 10 — Security Audit (Second Pass)

This pass targets questions `docs/PHASE-9-AUDIT.md` didn't ask: path
traversal internals, the full repo-wide subprocess surface, whether
prompt-injection defense is real code or just a policy doc, plugin
sandboxing depth, and frontend secret storage. Everything already
verified in Phase 9 (CORS, loopback binding, CRITICAL-tier
non-bypassability, credential encryption, IoT deny-by-default) is not
re-derived here.

## 1. Path traversal — real protection, correctly implemented

`services/computer-control/computer_control/filesystem/path_policy.py`,
`PathValidator.validate()`: rejects UNC/device paths (`\\server\share`,
`\\.\`, `\\?\`) via regex before any resolution; resolves the requested
path with `Path.resolve()` (which collapses `../` and follows symlinks to
their real target) and only then compares against pre-resolved
`allowed_roots` using `is_relative_to()`. This is the correct order of
operations — resolve first, then compare — which is what defeats both
`../../etc/passwd`-style traversal and a symlink planted inside an allowed
root that points outside it. `allowed_roots` are themselves pre-resolved
once at policy-construction time, avoiding a resolved-vs-unresolved
comparison bug. `engine.py` additionally blocks path separators in bare
names for `create_file`/`rename`, closing the `name="../evil"` variant.
**No gap found.**

## 2. Shell/subprocess execution — repo-wide, fully compliant

Exactly three production call sites touch `subprocess`/`Popen` in the
entire repository (not just local-api):

1. `computer_control/launcher.py:31` — `Popen([resolved, str(path)], shell=False)`;
   `resolved` is `shutil.which("xdg-open"/"open")` (a fixed name), `path`
   already validated by `PathValidator`.
2. `computer_control/windows/applications.py:51` — `Popen([str(resolved), *args], shell=False)`;
   `resolved` only ever comes from `ApplicationRegistry.resolve_executable_path()`,
   which resolves against a fixed `executable_candidates` allowlist per
   registry entry via `shutil.which()` — never an arbitrary model-supplied
   path.
3. `computer_control/windows/filesystem_launcher.py:19` — `os.startfile(path)`,
   not a shell invocation at all.

No `os.system`, `os.popen`, `shell=True`, or PowerShell/cmd invocation
exists anywhere in production code. CLAUDE.md's absolute rule ("No tool
executor may call subprocess... with model-originated or otherwise
unvalidated input") holds without exception, repo-wide.

## 3. Prompt-injection defense — a real, wired mechanism

`services/local-api/app/services/browser/security.py`:
`WebContentSanitizer.sanitize()` strips invisible/zero-width-character
smuggling and NFKC-normalizes; `InstructionBoundary.tag()` wraps every
payload as `{"text": ..., "source": ..., "trusted": may_authorize_action(source)}`
against the shared `veyra_contracts.TRUSTED_CONTENT_SOURCES` allowlist.
**Live call site**: `browser/tools.py:412` — every
`browser.extract_text`/`browser.get_page` result is sanitized and tagged
before it's returned. Since no real LLM provider exists yet, nothing
currently *consumes* the `trusted` flag to gate behavior — but the
mechanism, its contract, and its real caller against real browser output
all exist today. This is concrete implementation, not aspirational
documentation.

## 4. Plugin sandboxing — permission-flags only, no OS-level isolation

`PluginRegistry.enable()` registers a plugin's tool executor directly into
the same in-process `ToolRegistry` every built-in tool uses;
`ToolExecutor.execute()` is a plain `Protocol` with no subprocess,
container, restricted OS user, or resource limit around it. "Sandboxing"
today is default-deny permission flags (a plugin starts `UNTRUSTED`, every
permission ungranted, and `POST /plugins/install` can't supply a live
`tool_builder` at all over HTTP) — never true process/OS isolation. This
is an honest architectural limitation to carry forward and be explicit
about, not something to silently claim as fixed.

## 5. Frontend secret storage — clean

Zero occurrences of `localStorage`, `sessionStorage`, or `document.cookie`
anywhere in `apps/desktop/src`. Nothing credential-like — or anything
else — is persisted to browser storage.

## 6. Backup/recovery of local state — does not exist

No backup/export/restore mechanism exists anywhere for the database or
the credentials store. Confirmed absent; flagged as a real gap in
PRODUCTION-AUDIT.md, not attempted in this pass.

## 7. Deny-by-default for unknown tools/plugins — re-confirmed

`POST /tools/{id}/invoke` 404s on an unregistered tool ID
(`UnknownToolError`). `PluginRegistry.install()` always starts a plugin
`UNTRUSTED` with every permission ungranted; `grant()` refuses any
permission not present in the plugin's own manifest. Both already
verified in Phase 9 — re-confirmed unchanged here.

## Verdict

No new vulnerabilities found this pass. The two carried-forward
limitations worth remembering for future phases: plugin execution has no
OS-level isolation (permission flags only), and there is no backup/restore
story for local state yet.
