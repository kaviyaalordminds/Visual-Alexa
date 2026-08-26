"""docs/phase-5 §74-79 — ResponseGenerator's one hard rule: never say
"Done" when Phase 4 reports FAILED, never claim a CAPABILITY_UNAVAILABLE
task succeeded. Uses veyra_contracts.TaskState directly, exactly what a
real `Task` row would carry."""

from __future__ import annotations

from veyra_contracts import AmbiguityCandidate, ErrorCategory, ErrorInfo, TaskState
from voice.core.enums import Language
from voice.core.models import TaskOutcome
from voice.core.response import ResponseGenerator, generate_response


def test_completed_says_done():
    outcome = TaskOutcome(state=TaskState.COMPLETED, goal="Chrome")
    response = generate_response(outcome)
    assert response.should_speak is True
    assert "Done" in response.text


def test_failed_never_says_done():
    outcome = TaskOutcome(
        state=TaskState.FAILED,
        goal="open report.pdf",
        error=ErrorInfo.build(ErrorCategory.FILE_NOT_FOUND, "File not found.", "c1"),
    )
    response = generate_response(outcome)
    assert "Done" not in response.text
    assert "File not found." in response.text


def test_capability_unavailable_is_spoken_honestly_not_as_success():
    outcome = TaskOutcome(
        state=TaskState.FAILED,
        goal="turn on the AC",
        error=ErrorInfo.build(ErrorCategory.CAPABILITY_UNAVAILABLE, "No IoT capability.", "c2"),
    )
    response = generate_response(outcome)
    assert "capability" in response.text.lower()
    assert "Done" not in response.text


def test_cancelled_task_is_spoken():
    response = generate_response(TaskOutcome(state=TaskState.CANCELLED))
    assert response.should_speak is True
    assert "cancelled" in response.text.lower()


def test_timed_out_task_is_spoken():
    response = generate_response(TaskOutcome(state=TaskState.TIMED_OUT))
    assert "too long" in response.text.lower()


def test_waiting_user_speaks_the_real_clarifying_question_verbatim():
    outcome = TaskOutcome(
        state=TaskState.WAITING_USER, clarifying_question="Which file did you mean?"
    )
    response = generate_response(outcome)
    assert response.text == "Which file did you mean?"


def test_waiting_user_with_candidates_lists_them_when_no_question_text():
    outcome = TaskOutcome(
        state=TaskState.WAITING_USER,
        candidates=[
            AmbiguityCandidate(id="1", label="project1.txt"),
            AmbiguityCandidate(id="2", label="project2.txt"),
        ],
    )
    response = generate_response(outcome)
    assert "project1.txt" in response.text
    assert "project2.txt" in response.text


def test_waiting_permission_speaks_the_real_confirmation_prompt():
    outcome = TaskOutcome(
        state=TaskState.WAITING_PERMISSION,
        confirmation_prompt="Delete all files in Downloads. Risk: CRITICAL. Continue?",
    )
    response = generate_response(outcome)
    assert response.text == "Delete all files in Downloads. Risk: CRITICAL. Continue?"
    assert response.should_speak is True


def test_in_progress_states_are_silent_not_fabricated():
    for state in (TaskState.PLANNING, TaskState.EXECUTING, TaskState.OBSERVING):
        response = generate_response(TaskOutcome(state=state))
        assert response.should_speak is False
        assert response.text == ""


def test_tanglish_language_produces_tanglish_phrasing():
    outcome = TaskOutcome(state=TaskState.COMPLETED, goal="Chrome")
    response = generate_response(outcome, language=Language.TA_EN)
    assert response.language == Language.TA_EN
    assert response.text != generate_response(outcome, language=Language.EN).text


def test_generator_class_matches_pure_function():
    generator = ResponseGenerator()
    outcome = TaskOutcome(state=TaskState.COMPLETED)
    assert generator.generate(outcome).text == generate_response(outcome).text
