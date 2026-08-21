from __future__ import annotations

import time

import pytest

from app.services.import_deadline import Deadline, DeadlineExceededError


def test_deadline_start_computes_remaining_seconds_close_to_timeout():
    deadline = Deadline.start(10.0)
    assert 9.9 <= deadline.remaining_seconds() <= 10.0


def test_deadline_budget_for_side_effect_reserves_persistence_time():
    deadline = Deadline.start(10.0, persistence_reserve_seconds=5.0)
    assert 4.9 <= deadline.budget_for_side_effect() <= 5.0


def test_deadline_has_budget_for_side_effect_false_when_exhausted():
    deadline = Deadline.start(4.0, persistence_reserve_seconds=5.0)
    assert deadline.has_budget_for_side_effect(1.0) is False


def test_deadline_ensure_budget_raises_when_insufficient():
    deadline = Deadline.start(4.0, persistence_reserve_seconds=5.0)
    with pytest.raises(DeadlineExceededError):
        deadline.ensure_budget_for_side_effect(1.0)


def test_deadline_ensure_budget_passes_when_sufficient():
    deadline = Deadline.start(10.0, persistence_reserve_seconds=5.0)
    deadline.ensure_budget_for_side_effect(1.0)


def test_deadline_remaining_seconds_decreases_over_time():
    deadline = Deadline.start(1.0)
    before = deadline.remaining_seconds()
    time.sleep(0.05)
    after = deadline.remaining_seconds()
    assert after < before
