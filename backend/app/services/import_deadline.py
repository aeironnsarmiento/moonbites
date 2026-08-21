from __future__ import annotations

import time
from dataclasses import dataclass


class DeadlineExceededError(RuntimeError):
    pass


@dataclass(frozen=True)
class Deadline:
    monotonic_deadline: float
    persistence_reserve_seconds: float = 5.0

    @classmethod
    def start(
        cls, timeout_seconds: float, *, persistence_reserve_seconds: float = 5.0
    ) -> "Deadline":
        return cls(
            monotonic_deadline=time.monotonic() + timeout_seconds,
            persistence_reserve_seconds=persistence_reserve_seconds,
        )

    def remaining_seconds(self) -> float:
        return self.monotonic_deadline - time.monotonic()

    def budget_for_side_effect(self) -> float:
        return self.remaining_seconds() - self.persistence_reserve_seconds

    def has_budget_for_side_effect(self, min_seconds: float = 1.0) -> bool:
        return self.budget_for_side_effect() >= min_seconds

    def ensure_budget_for_side_effect(self, min_seconds: float = 1.0) -> None:
        if not self.has_budget_for_side_effect(min_seconds):
            raise DeadlineExceededError(
                "Not enough request budget remains for this side effect."
            )
