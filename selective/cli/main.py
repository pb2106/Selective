"""
Main CLI entrypoint for Selective (`selective`).
"""

import sys
import argparse
from selective.cli.commands import (
    cmd_scan,
    cmd_security,
    cmd_security_diff,
    cmd_explain,
    cmd_bisect,
    cmd_build,
    cmd_optimize,
    cmd_verify,
    cmd_doctor,
    cmd_install_hook,
    cmd_uninstall_hook,
    cmd_run,
)

def main():
    parser = argparse.ArgumentParser(prog="selective", description="Selective: Demand-Driven Package Loading & Optimization for Python")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    subparsers = parser.add_subparsers(dest="command", help="Selective CLI commands")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Analyze package or project AST statically")
    scan_parser.add_argument("target", nargs="?", default=".", help="Package name or project directory path (default: current directory)")
    scan_parser.add_argument("--project", action="store_true", help="Scan project directory and all its third-party package dependencies")
    scan_parser.add_argument("--bake", help="Bake relocatable cache to specified directory")

    # security
    sec_parser = subparsers.add_parser("security", help="Supply-chain security and behavioral analysis")
    sec_parser.add_argument("package", nargs="?", help="Package name or 'diff' command")
    sec_parser.add_argument("diff_target", nargs="?", help="Second report file path when running security diff")
    sec_parser.add_argument("--fail-on", help="CI policy threshold (LOW, MEDIUM, HIGH, CRITICAL)")

    # explain
    explain_parser = subparsers.add_parser("explain", help="Explain import safety decisions or causal chains")
    explain_parser.add_argument("name", help="Package or module name")
    explain_parser.add_argument("--unsafe", action="store_true", help="List only unsafe/eager edges")
    explain_parser.add_argument("--why", action="store_true", help="Explain complete causal chain for regression or eagerness")

    # bisect
    bisect_parser = subparsers.add_parser("bisect", help="Isolate failing lazy edge using automated bisection")
    bisect_parser.add_argument("script", help="Script path to bisect")

    # build
    build_parser = subparsers.add_parser("build", help="Build serverless or container optimization artifact")
    build_parser.add_argument("target", nargs="?", default=".", help="Target directory or entrypoint script")
    build_parser.add_argument("--type", default="generic", choices=["generic", "container", "lambda"], help="Optimization target environment type")
    build_parser.add_argument("--bake", help="Relocatable cache output directory")

    # optimize
    opt_parser = subparsers.add_parser("optimize", help="Optimize load plan under explicit performance budget")
    opt_parser.add_argument("target", help="Package name or script path")
    opt_parser.add_argument("--startup-target", default="500ms", help="Startup time target constraint (e.g. 500ms)")
    opt_parser.add_argument("--memory-target", default="300MB", help="Peak memory target constraint (e.g. 300MB)")
    opt_parser.add_argument("--safety", default="strict", choices=["strict", "balanced", "aggressive"], help="Safety policy mode")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Run differential verification")
    verify_parser.add_argument("script", help="Script path to verify")

    # doctor
    subparsers.add_parser("doctor", help="Run system diagnostics")

    # install-hook / uninstall-hook
    subparsers.add_parser("install-hook", help="Install sitecustomize / .pth hook in active venv")
    subparsers.add_parser("uninstall-hook", help="Uninstall sitecustomize / .pth hook")

    # run
    run_parser = subparsers.add_parser("run", help="Run script with Selective optimization enabled")
    run_parser.add_argument("--speculative", action="store_true", help="Enable background speculative loading during execution")
    run_parser.add_argument("-c", dest="code", default=None, help="Program passed in as string (like python -c)")
    run_parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Script and arguments")

    args = parser.parse_args()

    if args.command == "scan":
        sys.exit(cmd_scan(args.target, is_project=args.project, bake_dir=args.bake, json_out=args.json))
    elif args.command == "security":
        if args.package == "diff" and args.diff_target:
            # Handle 'selective security diff file1.json file2.json'
            # Note: in this case, args.diff_target is file1, remaining arg is file2 or handled via extra args
            sys.exit(cmd_security_diff(args.diff_target, sys.argv[-1], json_out=args.json))
        elif args.package and args.diff_target:
            # Handle 'selective security file1.json file2.json'
            sys.exit(cmd_security_diff(args.package, args.diff_target, json_out=args.json))
        elif args.package:
            sys.exit(cmd_security(args.package, fail_on=args.fail_on, json_out=args.json))
        else:
            sec_parser.print_help()
            sys.exit(0)
    elif args.command == "explain":
        sys.exit(cmd_explain(args.name, why=args.why, unsafe_only=args.unsafe, json_out=args.json))
    elif args.command == "bisect":
        sys.exit(cmd_bisect(args.script, json_out=args.json))
    elif args.command == "build":
        sys.exit(cmd_build(args.target, build_type=args.type, bake_dir=args.bake, json_out=args.json))
    elif args.command == "optimize":
        sys.exit(cmd_optimize(args.target, startup_target=args.startup_target, memory_target=args.memory_target, safety=args.safety, json_out=args.json))
    elif args.command == "verify":
        sys.exit(cmd_verify(args.script, json_out=args.json))
    elif args.command == "doctor":
        sys.exit(cmd_doctor(json_out=args.json))
    elif args.command == "install-hook":
        sys.exit(cmd_install_hook())
    elif args.command == "uninstall-hook":
        sys.exit(cmd_uninstall_hook())
    elif args.command == "run":
        sys.exit(cmd_run(args.script_args, speculative=args.speculative, code=args.code))
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
