"""Time scale constants and calendar utilities."""
from __future__ import annotations
from dataclasses import dataclass

# Fraction of a year per time scale
WEEK = 1 / 52
MONTH = 1 / 12
YEAR = 1.0

DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

@dataclass
class Calendar:
    year: int = 0
    month: int = 1
    day: int = 1

    def advance_fraction(self, delta_years: float) -> None:
        """Advance the calendar by ``delta_years``."""
        days = int(round(delta_years * 365))
        self.day += days
        while True:
            dim = DAYS_PER_MONTH[self.month - 1]
            if self.day <= dim:
                break
            self.day -= dim
            self.month += 1
            if self.month > 12:
                self.month = 1
                self.year += 1
