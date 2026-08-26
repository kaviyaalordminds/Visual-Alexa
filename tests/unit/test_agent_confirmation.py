"""docs/phase-4/CONFIRMATION.md — specific, understandable, time-limited,
escalating confirmation prompts (brief §21-23)."""

from __future__ import annotations

from app.services.agent.confirmation import ConfirmationManager
from veyra_contracts import PlanStep, RiskLevel, ToolCategory, ToolDefinition

_DEFINITION = ToolDefinition(
    id="filesystem.create_folder",
    name="Create Folder",
    description="Creates a folder.",
    category=ToolCategory.FILESYSTEM,
    input_schema={},
    output_schema={},
    risk_level=RiskLevel.MODERATE,
    required_permission="computer_control.filesystem.create_folder",
)


def test_prompt_names_the_exact_target_and_risk():
    step = PlanStep(
        sequence=1,
        description="Create folder",
        tool_id="filesystem.create_folder",
        arguments={"parent": "/a", "name": "reports"},
        risk_level=RiskLevel.MODERATE,
    )
    prompt = ConfirmationManager().build_prompt(step, _DEFINITION)
    assert "Create Folder" in prompt
    assert "MODERATE" in prompt


def test_prompt_is_not_generic():
    """docs/phase-4 §22 — 'Allow VEYRA?' is explicitly the bad example."""
    step = PlanStep(
        sequence=1,
        description="Open file",
        tool_id="filesystem.open",
        arguments={"path": "/a/project.pdf"},
        risk_level=RiskLevel.SAFE,
    )
    prompt = ConfirmationManager().build_prompt(step, _DEFINITION)
    assert prompt != "Allow VEYRA?"
    assert "/a/project.pdf" in prompt


def test_confirmation_expires_after_ttl():
    manager = ConfirmationManager()
    assert manager.confirmation_expired(301, ttl_seconds=300) is True
    assert manager.confirmation_expired(299, ttl_seconds=300) is False


def test_plan_change_to_different_target_requires_reconfirmation():
    """docs/phase-4 §23 — approved 'project.pdf', system found
    'project_final_confidential.pdf' instead: must ask again."""
    original = PlanStep(
        sequence=1, description="send", tool_id="filesystem.open",
        arguments={"path": "/a/project.pdf"}, risk_level=RiskLevel.SENSITIVE,
    )
    changed = PlanStep(
        sequence=1, description="send", tool_id="filesystem.open",
        arguments={"path": "/a/project_final_confidential.pdf"}, risk_level=RiskLevel.SENSITIVE,
    )
    assert ConfirmationManager().plan_changed_materially(original, changed) is True


def test_plan_unchanged_does_not_require_reconfirmation():
    original = PlanStep(
        sequence=1, description="send", tool_id="filesystem.open",
        arguments={"path": "/a/project.pdf"}, risk_level=RiskLevel.SENSITIVE,
    )
    same = PlanStep(
        sequence=1, description="send", tool_id="filesystem.open",
        arguments={"path": "/a/project.pdf"}, risk_level=RiskLevel.SENSITIVE,
    )
    assert ConfirmationManager().plan_changed_materially(original, same) is False
