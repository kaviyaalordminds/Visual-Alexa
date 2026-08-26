"""Precisely verifies the two reviewed subprocess call sites
(docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §5) actually satisfy the
property that matters: a list-literal argv (never a string built from
caller input) and `shell` never set to True. This is what makes it safe
for tests/security/test_no_unrestricted_shell.py to allow `subprocess` in
exactly these two files instead of banning it outright.
"""

from __future__ import annotations

import ast
import os

_CHECKED_FILES = (
    os.path.join(
        "services", "computer-control", "computer_control", "windows", "applications.py"
    ),
    os.path.join("services", "computer-control", "computer_control", "launcher.py"),
)

_SUBPROCESS_FUNCS = {"Popen", "run", "call", "check_call", "check_output"}


def _iter_subprocess_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_subprocess_call = (
            isinstance(func, ast.Attribute)
            and func.attr in _SUBPROCESS_FUNCS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        )
        if is_subprocess_call:
            yield node


def test_every_subprocess_call_uses_list_argv_and_shell_false(repo_root):
    violations: list[str] = []
    checked_any = False

    for relative_path in _CHECKED_FILES:
        full_path = os.path.join(repo_root, relative_path)
        assert os.path.isfile(full_path), f"Expected reviewed file missing: {full_path}"
        with open(full_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=full_path)

        for call in _iter_subprocess_calls(tree):
            checked_any = True
            location = f"{relative_path}:{call.lineno}"

            if not call.args or not isinstance(call.args[0], ast.List):
                violations.append(
                    f"{location}: first argument to subprocess.{call.func.attr} "
                    "must be a list literal, not a string or dynamic expression."
                )

            for keyword in call.keywords:
                if keyword.arg == "shell":
                    is_false = (
                        isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False
                    )
                    if not is_false:
                        violations.append(
                            f"{location}: shell= must be omitted or literally False, "
                            "never True or a dynamic value."
                        )

    assert checked_any, "No subprocess calls found in the reviewed files — update this test."
    assert not violations, "Unsafe subprocess call(s):\n" + "\n".join(violations)
