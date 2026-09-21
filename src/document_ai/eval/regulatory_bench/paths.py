"""Default paths for regulatory_bench."""

from __future__ import annotations

from pathlib import Path


def default_cases_root() -> Path:
    return Path("data/eval/regulatory_bench")


def default_reports_dir() -> Path:
    return Path("data/eval/regulatory_bench/reports")
