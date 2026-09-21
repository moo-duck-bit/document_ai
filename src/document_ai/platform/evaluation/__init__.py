"""Platform benchmark evaluation suite."""

__all__ = [
    "PlatformBenchmarkRunner",
    "compare_against_baseline",
    "compute_overall_score",
    "generate_markdown_report",
    "load_baseline",
    "load_benchmark_config",
    "save_baseline",
    "write_reports",
]


def __getattr__(name: str):
    if name == "PlatformBenchmarkRunner":
        from document_ai.platform.evaluation.benchmark_runner import PlatformBenchmarkRunner

        return PlatformBenchmarkRunner
    if name == "load_benchmark_config":
        from document_ai.platform.evaluation.benchmark_runner import load_benchmark_config

        return load_benchmark_config
    if name in {"load_baseline", "save_baseline"}:
        from document_ai.platform.evaluation import baseline as baseline_module

        return getattr(baseline_module, name)
    if name == "compare_against_baseline":
        from document_ai.platform.evaluation.regression import compare_against_baseline

        return compare_against_baseline
    if name == "compute_overall_score":
        from document_ai.platform.evaluation.metrics import compute_overall_score

        return compute_overall_score
    if name in {"generate_markdown_report", "write_reports"}:
        from document_ai.platform.evaluation import report_generator as report_module

        return getattr(report_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
