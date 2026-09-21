"""LEDGER adapter seam — stub today, real port later.

When full LEDGER consistency code arrives, implement ``LedgerConsistencyAdapter``
and swap ``run_consistency_column`` without changing scorecard CSV columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .consistency_stub import run_consistency_stub


class ConsistencyAdapter(Protocol):
    def run(self, case_dir: Path | str) -> dict[str, Any]:
        ...


class StubConsistencyAdapter:
    """Minimal regulatory redefinition of LEDGER reference/terminology/hierarchy."""

    name = "regulatory_consistency_stub_v0"
    full_ledger_port = False

    def run(self, case_dir: Path | str) -> dict[str, Any]:
        result = run_consistency_stub(case_dir)
        return {
            "adapter": self.name,
            "full_ledger_port": self.full_ledger_port,
            "pass": result["consistency_ok"],
            "score": result["consistency_score"],
            "checks": result["checks"],
            "ledger_analogue": result["ledger_analogue"],
        }


class LedgerConsistencyAdapter:
    """Placeholder for a future real LEDGER port."""

    name = "ledger_consistency_port"
    full_ledger_port = True

    def run(self, case_dir: Path | str) -> dict[str, Any]:
        raise NotImplementedError(
            "Full LEDGER port not wired. Use StubConsistencyAdapter "
            "(reference/terminology/hierarchy redefined for MDSR↔MDDR; no embedding θ)."
        )


def run_consistency_column(
    case_dir: Path | str,
    *,
    adapter: ConsistencyAdapter | None = None,
) -> dict[str, Any]:
    """Scorecard comparison column entrypoint."""
    impl = adapter or StubConsistencyAdapter()
    return impl.run(case_dir)
