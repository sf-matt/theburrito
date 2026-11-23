from __future__ import annotations

from typing import Protocol

from .models import SecurityAssessment, SecurityFinding


class Investigator(Protocol):
    """Provider-neutral boundary for one security-finding investigation."""

    def investigate(self, finding: SecurityFinding) -> SecurityAssessment: ...
