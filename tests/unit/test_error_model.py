"""Product brief §27 error model."""

from veyra_contracts import ErrorCategory, ErrorInfo


def test_network_error_is_retryable():
    err = ErrorInfo.build(ErrorCategory.NETWORK_ERROR, "connection reset", correlation_id="c1")
    assert err.retryable is True


def test_permission_denied_is_not_retryable():
    err = ErrorInfo.build(ErrorCategory.PERMISSION_DENIED, "denied", correlation_id="c2")
    assert err.retryable is False


def test_validation_error_is_not_retryable():
    err = ErrorInfo.build(ErrorCategory.VALIDATION_ERROR, "bad input", correlation_id="c3")
    assert err.retryable is False
