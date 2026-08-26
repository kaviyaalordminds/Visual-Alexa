"""UI element selector engine. docs/phase-2 §12: a fixed, typed set of
selector kinds — never arbitrary XPath-like expressions or unsafe string
execution. A selector is a set of exact-match criteria ANDed together;
there is no dynamic query language for a model to inject into.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from computer_control.core.models import UIElementInfo


class UISelector(BaseModel):
    automation_id: str | None = None
    name: str | None = None
    control_type: str | None = None
    class_name: str | None = None
    text: str | None = None
    # Scopes the search to a specific window rather than the whole desktop.
    window_title: str | None = None

    @model_validator(mode="after")
    def _at_least_one_criterion(self) -> UISelector:
        if not any([self.automation_id, self.name, self.control_type, self.class_name, self.text]):
            raise ValueError(
                "UISelector requires at least one of automation_id/name/"
                "control_type/class_name/text."
            )
        return self

    @classmethod
    def by_automation_id(cls, value: str, *, window_title: str | None = None) -> UISelector:
        return cls(automation_id=value, window_title=window_title)

    @classmethod
    def by_name(cls, value: str, *, window_title: str | None = None) -> UISelector:
        return cls(name=value, window_title=window_title)

    @classmethod
    def by_control_type(cls, value: str, *, window_title: str | None = None) -> UISelector:
        return cls(control_type=value, window_title=window_title)

    @classmethod
    def by_class_name(cls, value: str, *, window_title: str | None = None) -> UISelector:
        return cls(class_name=value, window_title=window_title)

    @classmethod
    def by_text(cls, value: str, *, window_title: str | None = None) -> UISelector:
        return cls(text=value, window_title=window_title)

    def matches(self, element: UIElementInfo) -> bool:
        """Pure matching logic shared by the fake backend and (structurally)
        by real backends' post-filtering — kept here so it's testable
        without any OS dependency."""
        if self.automation_id is not None and element.automation_id != self.automation_id:
            return False
        if self.name is not None and element.name != self.name:
            return False
        if self.control_type is not None and element.control_type != self.control_type:
            return False
        if self.class_name is not None and element.class_name != self.class_name:
            return False
        # `text` matches against the element's accessible name — VEYRA
        # models control text as UIElementInfo.name rather than a separate
        # field (most UIA/MSAA controls expose visible text as their Name
        # property); by_text() is kept as a distinct constructor because
        # "find by visible text" is a meaningfully different mental model
        # for a tool author than "find by accessible name", even though
        # they resolve the same way today.
        if self.text is not None and element.name != self.text:
            return False
        return True
