# -*- coding: utf-8 -*-
"""Regression: legacy runner/Pilot document_set_mode defaults."""

from __future__ import annotations

import inspect

from document_ai.pilot_ui import service
from document_ai.scenario.runner import run_user_scenario


def test_run_user_scenario_default_legacy_pair():
    sig = inspect.signature(run_user_scenario)
    assert sig.parameters["document_set_mode"].default == "legacy_pair"


def test_pilot_create_run_default_legacy():
    sig = inspect.signature(service.create_run)
    assert sig.parameters["document_set_mode"].default == "legacy_pair"


def test_pilot_execute_accepts_mode_kwarg():
    sig = inspect.signature(service.execute_run)
    assert "document_set_mode" in sig.parameters
