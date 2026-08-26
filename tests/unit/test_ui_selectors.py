"""docs/phase-2 §12 — a fixed, typed set of selector kinds; no arbitrary
XPath-like expressions, and a selector must name at least one criterion.
"""

import pytest
from computer_control.core.models import UIElementInfo
from computer_control.core.selectors import UISelector
from pydantic import ValidationError


def test_selector_requires_at_least_one_criterion():
    with pytest.raises(ValidationError):
        UISelector()


def test_by_automation_id_matches_only_that_id():
    element = UIElementInfo(automation_id="save-btn", name="Save")
    other = UIElementInfo(automation_id="cancel-btn", name="Cancel")
    selector = UISelector.by_automation_id("save-btn")
    assert selector.matches(element) is True
    assert selector.matches(other) is False


def test_by_name_matches_accessible_name():
    element = UIElementInfo(name="Save")
    selector = UISelector.by_name("Save")
    assert selector.matches(element) is True
    assert selector.matches(UIElementInfo(name="Cancel")) is False


def test_by_text_matches_against_name():
    element = UIElementInfo(name="Submit")
    selector = UISelector.by_text("Submit")
    assert selector.matches(element) is True


def test_multiple_criteria_are_all_required():
    selector = UISelector(name="Save", control_type="Button")
    assert selector.matches(UIElementInfo(name="Save", control_type="Button")) is True
    assert selector.matches(UIElementInfo(name="Save", control_type="MenuItem")) is False
