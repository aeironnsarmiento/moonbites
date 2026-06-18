from app.services.gemini.guardrails import GeminiGuardrails


def test_fourth_call_in_sixty_seconds_with_limit_three_is_rate_limited():
    guardrails = GeminiGuardrails()

    assert guardrails.allow_call("admin@example.com", limit=3, now=0.0) == (True, None)
    assert guardrails.allow_call("admin@example.com", limit=3, now=10.0) == (True, None)
    assert guardrails.allow_call("admin@example.com", limit=3, now=20.0) == (True, None)

    assert guardrails.allow_call("admin@example.com", limit=3, now=30.0) == (
        False,
        "rate_limited",
    )


def test_call_after_sixty_one_seconds_is_allowed():
    guardrails = GeminiGuardrails()

    assert guardrails.allow_call("admin@example.com", limit=3, now=0.0) == (True, None)
    assert guardrails.allow_call("admin@example.com", limit=3, now=10.0) == (True, None)
    assert guardrails.allow_call("admin@example.com", limit=3, now=20.0) == (True, None)

    assert guardrails.allow_call("admin@example.com", limit=3, now=61.0) == (True, None)


def test_five_failures_open_circuit_for_five_minutes():
    guardrails = GeminiGuardrails()

    for index in range(5):
        guardrails.record_failure(now=float(index))

    assert guardrails.allow_call("admin@example.com", limit=3, now=5.0) == (
        False,
        "circuit_open",
    )
    assert guardrails.allow_call("admin@example.com", limit=3, now=300.0) == (
        False,
        "circuit_open",
    )
    assert guardrails.allow_call("admin@example.com", limit=3, now=304.0) == (
        True,
        None,
    )


def test_success_resets_failure_count():
    guardrails = GeminiGuardrails()

    for index in range(4):
        guardrails.record_failure(now=float(index))

    guardrails.record_success()

    for index in range(4):
        guardrails.record_failure(now=10.0 + float(index))

    assert guardrails.allow_call("admin@example.com", limit=3, now=20.0) == (True, None)


def test_rate_limit_is_per_key_not_global():
    guardrails = GeminiGuardrails()

    assert guardrails.allow_call("first@example.com", limit=1, now=0.0) == (True, None)
    assert guardrails.allow_call("first@example.com", limit=1, now=1.0) == (
        False,
        "rate_limited",
    )

    assert guardrails.allow_call("second@example.com", limit=1, now=1.0) == (True, None)
