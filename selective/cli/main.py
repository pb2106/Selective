"""
Main CLI entrypoint for Selective (`selective`).
"""

import sys
import argparse
from selective.cli.commands import (
    cmd_scan,
    cmd_explain,
    cmd_verify,
    cmd_doctor,
    cmd_install_hook,
    cmd_uninstall_hook,
    cmd_run,
)

def main():
    parser = argparse.ArgumentParser(prog="selective", description="Selective: Demand-Driven Package Loading for Python")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    subparsers = parser.add_subparsers(dest="command", help="Selective CLI commands")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Analyze package or project AST statically")
    scan_parser.add_argument("target", nargs="?", default=".", help="Package name or project directory path (default: current directory)")
    scan_parser.add_argument("--project", action="store_true", help="Scan project directory and all its third-party package dependencies")
    scan_parser.add_argument("--bake", help="Bake relocatable cache to specified directory")

    # explain
    explain_parser = subparsers.add_parser("explain", help="Explain import safety decisions")
    explain_parser.add_argument("name", help="Package or module name")
    explain_parser.add_argument("--unsafe", action="store_true", help="List only unsafe/eager edges")

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
    run_parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Script and arguments")

    args = parser.parse_args()

    if args.command == "scan":
        sys.exit(cmd_scan(args.target, is_project=args.project, bake_dir=args.bake, json_out=args.json))
    elif args.command == "explain":
        sys.exit(cmd_explain(args.name, unsafe_only=args.unsafe, json_out=args.json))
    elif args.command == "verify":
        sys.exit(cmd_verify(args.script, json_out=args.json))
    elif args.command == "doctor":
        sys.exit(cmd_doctor(json_out=args.json))
    elif args.command == "install-hook":
        sys.exit(cmd_install_hook())
    elif args.command == "uninstall-hook":
        sys.exit(cmd_uninstall_hook())
    elif args.command == "run":
        sys.exit(cmd_run(args.script_args))
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
