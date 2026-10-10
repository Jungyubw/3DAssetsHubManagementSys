"""assethub-importer CLI. See docs/SPEC.md for each command."""
from __future__ import annotations

import argparse
import sys

from rich.console import Console

from importer.config import load_settings

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assethub-importer")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory", help="List all GLB files in shared drives -> inventory.csv (read-only)")
    sub.add_parser("hub-snapshot", help="Snapshot hub projects/assets -> hub_assets.csv (read-only)")
    sub.add_parser("plan", help="Apply rules -> plan.csv and per-project summary (read-only)")

    apply = sub.add_parser("apply", help="Create projects and upload assets (writes to hub)")
    apply.add_argument("--project", required=True, help="Hub project name to process")
    apply.add_argument("--limit", type=int, default=None, help="Max files to upload")
    apply.add_argument("--yes", action="store_true", help="Actually write; without it, only print the plan")

    sub.add_parser("verify", help="Compare ledger with hub (read-only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_settings()
    try:
        if args.command == "apply" and not args.yes:
            console.print("[yellow]Dry run[/] (--yes not given): nothing will be written to the hub.")
        raise NotImplementedError(f"'{args.command}' is not implemented yet")
    except NotImplementedError as e:
        console.print(f"[red]{e}[/]")
        return 2


if __name__ == "__main__":
    sys.exit(main())
