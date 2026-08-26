"""ConfirmationManager — builds specific, understandable confirmation
prompts. docs/phase-4/CONFIRMATION.md.

Does not decide *whether* confirmation is required or evaluate any grant
— that is the Policy Engine's job alone
(docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §6), unconditionally, for
every step, with no orchestrator-side bypass. This module only turns a
`PolicyDecision(requires_confirmation=True)` plus the step that triggered
it into the exact, non-paraphrased text
docs/security/08-SENSITIVE-ACTION-POLICY.md §3 requires: the tool/action,
the target, the risk tier, and a plain-language reason.
"""

from __future__ import annotations

from veyra_contracts import PlanStep, RiskLevel, ToolDefinition


class ConfirmationManager:
    def build_prompt(self, step: PlanStep, definition: ToolDefinition) -> str:
        target = step.arguments.get("path") or step.arguments.get("application") or step.description
        reason = {
            RiskLevel.MODERATE: "This makes a reversible change.",
            RiskLevel.SENSITIVE: "This has an externally visible or harder-to-reverse effect.",
            RiskLevel.CRITICAL: "This is destructive or irreversible.",
        }.get(step.risk_level, "")
        return (
            f"{definition.name} — {target}. "
            f"Risk: {step.risk_level.value}. {reason} Continue?"
        ).strip()

    def confirmation_expired(
        self, requested_at_seconds_ago: float, *, ttl_seconds: float = 300
    ) -> bool:
        """docs/phase-4 §22 — 'time-limited.' A confirmation prompt older
        than `ttl_seconds` must be re-issued, never silently honored."""
        return requested_at_seconds_ago > ttl_seconds

    def plan_changed_materially(self, original_step: PlanStep, new_step: PlanStep) -> bool:
        """docs/phase-4 §23 — confirmation escalation: if the concrete
        target changed after the user approved a step, the approval no
        longer covers it. Compared by tool_id + the same target fields
        `build_prompt` displays, so 'what the user saw' is exactly 'what
        changed' — never the full argument dict (which may include
        cosmetic differences the user never saw)."""
        if original_step.tool_id != new_step.tool_id:
            return True
        original_target = original_step.arguments.get("path") or original_step.arguments.get(
            "application"
        )
        new_target = new_step.arguments.get("path") or new_step.arguments.get("application")
        return original_target != new_target
