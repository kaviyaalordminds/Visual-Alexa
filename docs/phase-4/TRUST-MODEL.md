# Trust Model

## 1. Reused unchanged from Phase 3

`veyra_contracts.enums.ContentSource` + `TRUSTED_CONTENT_SOURCES`
(defined in Phase 3, `docs/phase-3/PROMPT-INJECTION.md` §3) are reused
directly, not replaced. The brief's §38 names are aliases for values that
already exist:

| Brief name | This codebase |
|---|---|
| `USER_INSTRUCTION` | `USER` / `USER_INPUT` |
| `SYSTEM_INSTRUCTION` | `SYSTEM` / `SYSTEM_STATE` |
| `MODEL_OUTPUT` | `AI_OUTPUT` |
| `POLICY`, `TOOL_RESULT`, `UI_OBSERVATION`, `WEB_CONTENT`, `DOCUMENT_CONTENT` | identical |

A second, parallel trust-label enum was deliberately rejected — see
`PHASE-4-IMPLEMENTATION-PLAN.md` §1: fragmenting "which sources may
authorize an action" into two enums would let one drift from the other.
`TRUSTED_CONTENT_SOURCES = {USER, USER_INPUT, SYSTEM, SYSTEM_STATE}`
remains the single place that question is answered.

## 2. Source of truth (brief §80)

| Concern | Source of truth |
|---|---|
| Task state | `TaskStateMachine` (this phase) |
| Permissions | `PolicyEngine` (Phase 1) |
| Windows actions | Phase 2 tools |
| Screen/perception | Phase 3 tools |
| AI reasoning | `LLMProvider` — advisory only, see below |

**The LLM is never the source of truth for system state** — and in Phase
4 this is trivially, structurally true: no LLM is even configured
(`NotConfiguredLLMProvider`), so there is no reasoning output that could
be mistaken for ground truth. The principle is enforced in code today by
the fact that `TaskState` transitions are driven exclusively by real
`ToolResult`s (see §3) — when a real provider is added, that enforcement
must not change.

## 3. Hallucinated file / hallucinated success (brief §78-79)

- **Hallucinated file claims**: `TaskPlanner`'s `open_file` template
  never trusts a claimed filename — it only ever acts on what
  `filesystem.search` (real filesystem I/O, through the real Policy
  Engine) actually returns.
- **Hallucinated success**: `AgentOrchestrator._execute_plan` reads only
  `ToolResult.status`; nothing about a step's own `description` text (even
  one deliberately reading "Successfully completed.") ever influences
  `TaskState`. Verified directly:
  `tests/security/test_agent_adversarial.py::test_fake_success_never_overrides_real_tool_failure`
  plants exactly that lie in a step's description, targets a file that
  doesn't exist, and confirms the task still ends `FAILED`.

## 4. `WEB_CONTENT`/`UI_OBSERVATION` never authorize an action

Unchanged from Phase 3, restated here because Phase 4 is the phase where
"authorize an action" first has real meaning (Phase 3 only perceived;
Phase 4 executes). No code path in `app/services/agent/` ever treats
`ContentSource.WEB_CONTENT` or `UI_OBSERVATION` as equivalent to
`USER_INPUT` when deciding what to plan or execute.
