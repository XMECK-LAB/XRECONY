from __future__ import annotations

import json
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .scanner import reconstruct


def run_suite(source: str, output: str, runs: int = 5, cache: str = "unspecified") -> dict:
    if runs < 3 or runs > 25:
        raise ValueError("runs must be between 3 and 25")
    target = Path(output).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    samples = []
    for index in range(1, runs + 1):
        workspace = target / "runs" / f"run-{index:02d}"
        result = reconstruct(
            source,
            str(workspace),
            mode="benchmark",
            cold_warm_declaration=cache,
        )
        benchmark = result["benchmark"]
        samples.append(
            {
                "run": index,
                "generation_id": benchmark["generation_id"],
                "elapsed_seconds": benchmark["timing"]["elapsed_seconds"],
                "records_per_second": benchmark["timing"]["records_per_second"],
                "integrity": benchmark["integrity"]["state"],
            }
        )
    rates = [sample["records_per_second"] for sample in samples]
    times = [sample["elapsed_seconds"] for sample in samples]
    report = {
        "format": "xrecony-controlled-benchmark-suite-v3-candidate",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(Path(source).expanduser().resolve()),
        "runs": runs,
        "cache_declaration": cache,
        "environment": {"platform": platform.platform(), "adapter": "python-optimized-scandir-v3"},
        "statistics": {
            "records_per_second": {
                "minimum": min(rates),
                "maximum": max(rates),
                "median": statistics.median(rates),
                "mean": statistics.fmean(rates),
                "population_stddev": statistics.pstdev(rates),
            },
            "elapsed_seconds": {
                "minimum": min(times),
                "maximum": max(times),
                "median": statistics.median(times),
            },
        },
        "samples": samples,
        "claim_eligible": False,
        "claim_boundary": "Reference-adapter suite; independent native and comparative evidence is still required.",
    }
    report_path = target / "XRECONY_BENCHMARK_SUITE.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
