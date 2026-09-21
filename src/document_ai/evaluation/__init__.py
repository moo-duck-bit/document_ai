# -*- coding: utf-8 -*-
"""Document Set Benchmark evaluation package (PR-28)."""

from document_ai.evaluation.document_set.evaluator import run_benchmark
from document_ai.evaluation.document_set.dataset_loader import load_benchmark_manifest

__all__ = ["run_benchmark", "load_benchmark_manifest"]
