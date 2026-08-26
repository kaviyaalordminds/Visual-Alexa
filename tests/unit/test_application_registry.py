"""docs/phase-2 §6.2, §6.3, §20 — 'Open Chrome' resolves alias -> known
application -> discovered executable -> launch. Unknown names never reach
a launch call.
"""

import pytest
from computer_control.registry import (
    ApplicationDisabledError,
    ApplicationNotFoundError,
    ApplicationRegistry,
    ApplicationRegistryEntry,
)
from veyra_contracts import RiskLevel


@pytest.fixture
def registry():
    return ApplicationRegistry(
        [
            ApplicationRegistryEntry(
                identifier="python_app",
                name="Python Test App",
                aliases=("python", "python3"),
                executable_candidates=("python3",),
                risk_level=RiskLevel.SAFE,
            ),
            ApplicationRegistryEntry(
                identifier="disabled_app",
                name="Disabled App",
                executable_candidates=("does-not-exist-binary",),
                enabled=False,
            ),
        ]
    )


def test_resolve_by_identifier_name_or_alias(registry):
    for query in ("python_app", "Python Test App", "python", "python3", "PYTHON"):
        path = registry.resolve(query)
        assert path.endswith("python3") or "python3" in path


def test_unknown_application_is_denied(registry):
    with pytest.raises(ApplicationNotFoundError):
        registry.resolve("totally-unknown-app.exe")


def test_disabled_application_is_denied_even_though_registered(registry):
    with pytest.raises(ApplicationDisabledError):
        registry.resolve("disabled_app")


def test_unresolvable_executable_raises_not_found():
    registry = ApplicationRegistry(
        [
            ApplicationRegistryEntry(
                identifier="ghost",
                name="Ghost App",
                executable_candidates=("this-binary-does-not-exist-anywhere",),
            )
        ]
    )
    with pytest.raises(ApplicationNotFoundError):
        registry.resolve("ghost")
