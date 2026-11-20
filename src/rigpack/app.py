from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rigpack.core import RigPackStore
from rigpack.registry import all_known_specs, detect_targets
from rigpack.tui import run_tui

ACCENT = "#FF4500"
FG = "#F5F5F5"
MUTED = "#9A9A9A"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rigpack",
        description="Auto-detect game & dev configs, backup to managed cloud, diff changes & restore via CLI or TUI.",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("ui", help="Launch the interactive brutalist terminal UI")

    p_scan = sub.add_parser("scan", help="Auto-detect installed games and dev app configs on this PC")
    p_scan.add_argument("game_or_app", nargs="?", default=None, help="Optional game/app name or alias")
    p_scan.add_argument("--cat", choices=["GAME", "DEV", "game", "dev"], default=None, help="Filter by category")
    p_scan.add_argument("--register", action="store_true", help="Automatically register all detected targets as profiles")

    p_add = sub.add_parser("add", help="Register a custom file/folder or auto-detect by game/app name")
    p_add.add_argument("name", help="Profile name OR known game/app name")
    p_add.add_argument("targets", nargs="*", help="Explicit file/dir paths (optional if auto-detected)")
    p_add.add_argument("--cat", default="CUSTOM", help="Category label (GAME, DEV, CUSTOM)")
    p_add.add_argument("--ignore", nargs="*", default=[], help="Extra ignore patterns")

    p_rm = sub.add_parser("rm", help="Remove a registered profile")
    p_rm.add_argument("name", help="Profile name")

    sub.add_parser("list", help="List registered profiles")

    p_snap = sub.add_parser("snap", help="Snapshot a profile and upload bundle to zero-setup cloud")
    p_snap.add_argument("name", help="Profile name or known game/app name")
    p_snap.add_argument("--local-only", action="store_true", help="Save locally without uploading to cloud")

    p_push = sub.add_parser("push", help="Upload an existing snapshot bundle to the cloud")
    p_push.add_argument("name", help="Profile name")
    p_push.add_argument("--snap", default=None, help="Snapshot ID (defaults to latest)")

    p_pull = sub.add_parser("pull", help="Download a cloud snapshot bundle onto this machine")
    p_pull.add_argument("name", help="Profile name")
    p_pull.add_argument("--url", default=None, help="Direct cloud bundle URL (defaults to latest recorded URL)")

    p_snaps = sub.add_parser("snaps", help="List snapshot history and cloud URLs for a profile")
    p_snaps.add_argument("name", help="Profile name")

    p_diff = sub.add_parser("diff", help="Show modified, added, and missing files vs snapshot")
    p_diff.add_argument("name", help="Profile name")
    p_diff.add_argument("--snap", default=None, help="Snapshot ID (defaults to latest)")

    p_restore = sub.add_parser("restore", help="Restore a profile from snapshot")
    p_restore.add_argument("name", help="Profile name")
    p_restore.add_argument("--snap", default=None, help="Snapshot ID (defaults to latest)")
    p_restore.add_argument("--no-backup", action="store_true", help="Skip automatic safety backup before restore")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console()
    store = RigPackStore()

    if args.command in (None, "ui"):
        return run_tui(store)

    try:
        if args.command == "scan":
            found = detect_targets(query=args.game_or_app, category=args.cat)
            table = Table(
                title=f"DETECTED TARGETS ({len(found)})",
                border_style=ACCENT,
                header_style=f"bold {ACCENT}",
            )
            table.add_column("KEY", style=f"bold {FG}", width=18)
            table.add_column("CAT", style=f"bold {ACCENT}", width=7)
            table.add_column("NAME", style=FG, width=32)
            table.add_column("DETECTED PATHS", style=MUTED)

            for d in found:
                table.add_row(d.key, d.category, d.display_name, "\n".join(d.detected_paths))

            console.print(table)
            if not found:
                known_keys = ", ".join(s.key for s in all_known_specs(args.cat))
                console.print(f"[{MUTED}]No live paths found on disk for that query. Known specs: {known_keys}[/{MUTED}]")
                return 0

            if args.register:
                regs = store.auto_register(game_or_app_query=args.game_or_app, category=args.cat)
                console.print(f"[{ACCENT}]Auto-registered {len(regs)} profile(s).[/{ACCENT}]")
            return 0

        if args.command == "add":
            if not args.targets:
                matched = detect_targets(query=args.name)
                if not matched:
                    raise FileNotFoundError(
                        f"No existing config paths auto-detected for '{args.name}'. Pass explicit paths: rigpack add {args.name} <path...>"
                    )
                top = matched[0]
                entry = store.add_profile(top.key, top.detected_paths, category=top.category, ignore=top.ignore + args.ignore)
            else:
                entry = store.add_profile(args.name, args.targets, category=args.cat, ignore=args.ignore)

            console.print(
                Panel(
                    f"[bold {FG}]Profile:[/bold {FG}]  {entry.name} ({entry.category})\n"
                    f"[bold {FG}]Targets:[/bold {FG}]  " + "\n          ".join(entry.targets),
                    title=f"[bold {ACCENT}]RIGPACK // PROFILE REGISTERED[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

        if args.command == "rm":
            store.remove_profile(args.name)
            console.print(f"[{ACCENT}]Removed profile:[/{ACCENT}] {args.name}")
            return 0

        if args.command == "list":
            profiles = store.list_profiles()
            table = Table(
                title=f"RIGPACK PROFILES ({len(profiles)})",
                border_style=ACCENT,
                header_style=f"bold {ACCENT}",
            )
            table.add_column("PROFILE", style=f"bold {FG}", width=18)
            table.add_column("CAT", style=f"bold {ACCENT}", width=8)
            table.add_column("LATEST SNAP", style=FG, width=18)
            table.add_column("TARGETS", style=MUTED)

            for p in profiles:
                snaps = store.list_snapshots(p.name)
                latest = snaps[0]["snapshot_id"] if snaps else "none"
                table.add_row(p.name, p.category, latest, "\n".join(p.targets))

            console.print(table)
            return 0

        if args.command == "snap":
            try:
                store.get_profile(args.name)
            except KeyError:
                matched = detect_targets(query=args.name)
                if matched:
                    top = matched[0]
                    store.add_profile(top.key, top.detected_paths, category=top.category, ignore=top.ignore)
                    args.name = top.key
                else:
                    raise

            rec = store.snapshot(args.name, push_cloud=not args.local_only)
            cloud_line = f"\n[bold {FG}]Cloud URL:[/bold {FG}] {rec.cloud_url}" if rec.cloud_url else ""
            console.print(
                Panel(
                    f"[bold {FG}]Profile:[/bold {FG}]  {rec.profile}\n"
                    f"[bold {FG}]Snapshot:[/bold {FG}] {rec.snapshot_id}\n"
                    f"[bold {FG}]Files:[/bold {FG}]    {len(rec.files)} tracked (SHA-256 verified){cloud_line}",
                    title=f"[bold {ACCENT}]RIGPACK // SNAPSHOT SAVED[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

        if args.command == "push":
            ref = store.push_snapshot_to_cloud(args.name, snap_id=args.snap)
            console.print(
                Panel(
                    f"[bold {FG}]Bundle:[/bold {FG}] {ref.bundle_id}\n"
                    f"[bold {FG}]URL:[/bold {FG}]    {ref.url}",
                    title=f"[bold {ACCENT}]RIGPACK // UPLOADED TO CLOUD[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

        if args.command == "pull":
            sid = store.pull_from_cloud(args.name, url=args.url)
            console.print(
                Panel(
                    f"[bold {FG}]Profile:[/bold {FG}]  {args.name}\n"
                    f"[bold {FG}]Pulled:[/bold {FG}]   {sid}",
                    title=f"[bold {ACCENT}]RIGPACK // PULLED FROM CLOUD[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

        if args.command == "snaps":
            snaps = store.list_snapshots(args.name)
            table = Table(
                title=f"SNAPSHOTS // {args.name}",
                border_style=ACCENT,
                header_style=f"bold {ACCENT}",
            )
            table.add_column("SNAPSHOT ID", style=f"bold {FG}")
            table.add_column("CREATED", style=MUTED)
            table.add_column("FILES", style=FG)
            table.add_column("CLOUD URL", style=FG)
            for s in snaps:
                table.add_row(s["snapshot_id"], s["created_at"], str(s["file_count"]), s.get("cloud_url") or "local-only")
            console.print(table)
            return 0

        if args.command == "diff":
            changes = store.diff(args.name, snap_id=args.snap)
            out = Text()
            for bucket, label, style in [
                ("modified", "MODIFIED", f"bold {ACCENT}"),
                ("added", "ADDED", f"bold {FG}"),
                ("missing", "MISSING", f"bold {MUTED}"),
            ]:
                items = changes[bucket]
                out.append(f"{label} ({len(items)})\n", style=style)
                if not items:
                    out.append("  none\n", style=MUTED)
                else:
                    for item in items:
                        out.append(f"  - {item}\n", style=FG)
            console.print(
                Panel(
                    out,
                    title=f"[bold {ACCENT}]RIGPACK // DRIFT DIFF ({args.name})[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

        if args.command == "restore":
            snap_used, count = store.restore(args.name, snap_id=args.snap, backup_current=not args.no_backup)
            console.print(
                Panel(
                    f"[bold {FG}]Profile:[/bold {FG}]   {args.name}\n"
                    f"[bold {FG}]Restored:[/bold {FG}]  {snap_used}\n"
                    f"[bold {FG}]Files:[/bold {FG}]     {count} file(s) written back",
                    title=f"[bold {ACCENT}]RIGPACK // RESTORE COMPLETE[/bold {ACCENT}]",
                    border_style=ACCENT,
                )
            )
            return 0

    except (FileNotFoundError, KeyError, ValueError, RuntimeError, OSError) as exc:
        console.print(f"[bold {ACCENT}]Error:[/bold {ACCENT}] {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
