from __future__ import annotations

import argparse
import json

from .fixtures import build_scale_fixture
from .benchmark_suite import run_suite
from .scanner import reconstruct
from .server import run_server
from .verify import verify_generation


def main(argv=None):
    parser = argparse.ArgumentParser(prog="xrecony", description="XRECONY Reconstruction Fabric One")
    subs = parser.add_subparsers(dest="command", required=True)
    serve = subs.add_parser("serve", help="Run the local dashboard")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open-browser", action="store_true")
    scan = subs.add_parser("scan", help="Create a Reconstruction Twin generation")
    scan.add_argument("source")
    scan.add_argument("--workspace", required=True)
    scan.add_argument("--mode", choices=("normal", "benchmark"), default="normal")
    scan.add_argument("--cache", choices=("unspecified", "cold", "warm"), default="unspecified")
    verify = subs.add_parser("verify", help="Verify a generation receipt and accounting")
    verify.add_argument("generation_dir")
    fixture = subs.add_parser("fixture", help="Create a deterministic metadata-scale test fixture")
    fixture.add_argument("target")
    fixture.add_argument("--records", type=int, default=10000)
    fixture.add_argument("--payload-bytes", type=int, default=0)
    benchmark = subs.add_parser("benchmark", help="Run a disclosed repeated benchmark suite")
    benchmark.add_argument("source")
    benchmark.add_argument("--output", required=True)
    benchmark.add_argument("--runs", type=int, default=5)
    benchmark.add_argument("--cache", choices=("unspecified", "cold", "warm"), default="unspecified")
    args = parser.parse_args(argv)
    if args.command == "serve":
        run_server(args.port, args.open_browser)
        return 0
    if args.command == "scan":
        print(json.dumps(reconstruct(args.source, args.workspace, mode=args.mode, cold_warm_declaration=args.cache), indent=2))
        return 0
    if args.command == "fixture":
        print(json.dumps(build_scale_fixture(args.target, args.records, args.payload_bytes), indent=2))
        return 0
    if args.command == "benchmark":
        print(json.dumps(run_suite(args.source, args.output, args.runs, args.cache), indent=2))
        return 0
    result = verify_generation(args.generation_dir)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid") else 1
