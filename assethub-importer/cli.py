"""assethub-importer CLI. See docs/SPEC.md for each command."""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from importer import drive, hub, plan, rules
from importer.config import ROOT, Settings, load_settings
from importer.csvio import read_csv, write_csv
from importer.ledger import Ledger

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assethub-importer")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory", help="List all GLB files in shared drives -> inventory.csv (read-only)")
    sub.add_parser("hub-snapshot", help="Snapshot hub projects/assets -> hub_assets.csv (read-only)")
    p = sub.add_parser("plan", help="Apply rules -> plan.csv and per-project summary (read-only)")
    p.add_argument("--without-hub", action="store_true",
                   help="Plan without hub_assets.csv (hub treated as empty; for rule checks only)")

    apply = sub.add_parser("apply", help="Create projects and upload assets (writes to hub)")
    apply.add_argument("--project", required=True, help="Hub project name to process")
    apply.add_argument("--limit", type=int, default=None, help="Max files to upload")
    apply.add_argument("--yes", action="store_true", help="Actually write; without it, only print the plan")

    sub.add_parser("verify", help="Compare ledger with hub (read-only)")
    return parser


def cmd_inventory(s: Settings) -> None:
    sel = s.config["selection"]
    service = drive.build_service(s)
    with console.status("Listing GLB files in all shared drives…") as status:
        files = drive.list_glb_files(
            service, sel["extensions"], sel["mime_types"],
            on_progress=lambda name: status.update(f"Building folder paths: {name}"),
        )
    out = s.output_dir / "inventory.csv"
    write_csv(out, [asdict(f) for f in files], drive.INVENTORY_COLUMNS)
    drives = {f.shared_drive for f in files}
    total_gb = sum(f.size_bytes for f in files) / 1e9
    console.print(f"[green]{len(files):,} GLB files[/] in {len(drives)} shared drives, {total_gb:.1f}GB -> {out}")


def cmd_hub_snapshot(s: Settings) -> None:
    client = hub.HubClient(s.assethub_api_base, s.assethub_token)
    projects = client.list_projects()
    with console.status("Listing hub assets…") as status:
        items = client.list_assets(on_page=lambda n, total: status.update(f"Listing hub assets… {n}/{total}"))
        status.update(f"Fetching {len(items)} asset details…")
        details = client.get_assets([i["id"] for i in items], s.config["limits"]["hub_detail_concurrency"])
    rows = [r for item, d in zip(items, details) for r in hub.flatten_asset({**item, **d})]
    write_csv(s.output_dir / "hub_projects.csv",
              [{"project_id": p.get("id", ""), "name": p.get("name", ""), "status": p.get("status", "")} for p in projects],
              hub.HUB_PROJECT_COLUMNS)
    write_csv(s.output_dir / "hub_assets.csv", rows, hub.HUB_ASSET_COLUMNS)
    console.print(f"[green]{len(projects)} projects, {len(items)} assets, {len(rows)} files[/] -> {s.output_dir}")


def cmd_plan(s: Settings, without_hub: bool) -> None:
    out = s.output_dir
    inv_path = out / "inventory.csv"
    if not inv_path.exists():
        raise SystemExit("inventory.csv not found. Run `inventory` first.")
    hub_assets_path, hub_projects_path = out / "hub_assets.csv", out / "hub_projects.csv"
    if without_hub:
        hub_assets, hub_projects = [], []
        console.print("[yellow]--without-hub: hub treated as empty. Do not apply this plan.[/]")
    elif not hub_assets_path.exists():
        raise SystemExit("hub_assets.csv not found. Run `hub-snapshot` first, or use --without-hub for rule checks.")
    else:
        hub_assets, hub_projects = read_csv(hub_assets_path), read_csv(hub_projects_path)
    mapping_path = ROOT / "mapping.csv"
    mapping = read_csv(mapping_path) if mapping_path.exists() else []

    rows = plan.build_plan(read_csv(inv_path), hub_assets, hub_projects, mapping, s.config)
    summary = plan.summarize(rows)
    write_csv(out / "plan.csv", rows, plan.PLAN_COLUMNS)
    write_csv(out / "plan_summary.csv", summary, list(summary[0]) if summary else ["hub_project"])
    if not without_hub:
        kept = Ledger(ROOT / s.config["ledger_db"]).upsert_plan(rows)
        if kept:
            console.print(f"{kept} rows already uploaded/verified were left unchanged in the ledger.")

    table = Table(title="Plan by hub project")
    for col in ["hub_project", "new_project", *rules.DECISIONS, "register_mb"]:
        table.add_column(col, justify="left" if col == "hub_project" else "right")
    for r in summary:
        table.add_row(*(str(r[c]) for c in ["hub_project", "new_project", *rules.DECISIONS, "register_mb"]))
    console.print(table)
    totals = {d: sum(r[d] for r in summary) for d in rules.DECISIONS}
    console.print(" · ".join(f"{d} {n:,}" for d, n in totals.items()))
    console.print(f"-> {out / 'plan.csv'}, {out / 'plan_summary.csv'}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    s = load_settings()
    try:
        if args.command == "inventory":
            cmd_inventory(s)
        elif args.command == "hub-snapshot":
            cmd_hub_snapshot(s)
        elif args.command == "plan":
            cmd_plan(s, args.without_hub)
        else:
            if args.command == "apply" and not args.yes:
                console.print("[yellow]Dry run[/] (--yes not given): nothing will be written to the hub.")
            raise NotImplementedError(f"'{args.command}' waits for the AssetHub write API spec (docs/SPEC.md)")
    except (NotImplementedError, hub.HubAuthError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
