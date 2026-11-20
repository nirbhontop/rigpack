from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rigpack.core import RigPackStore
from rigpack.registry import detect_targets

BG = "#0D0D0D"
SURFACE = "#141414"
BORDER_DIM = "#262626"
ACCENT = "#FF4500"
FG = "#F5F5F5"
MUTED = "#9A9A9A"


@dataclass
class UiState:
    tab: int = 0
    cursor: int = 0
    status_msg: str = "READY — [TAB] VIEW  [J/K] MOVE  [A] AUTO-ADD  [S] CLOUD-SNAP  [R] RESTORE  [Q] QUIT"


if os.name == "nt":
    import msvcrt

    def _read_key() -> str:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ext = msvcrt.getwch()
            if ext == "H":
                return "UP"
            if ext == "P":
                return "DOWN"
            return "ESC"
        if ch == "\t":
            return "TAB"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        return ch
else:
    import termios
    import tty

    def _read_key() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "UP"
                if seq == "[B":
                    return "DOWN"
                if seq == "[Z":
                    return "SHIFT_TAB"
                return "ESC"
            if ch == "\t":
                return "TAB"
            if ch in ("\r", "\n"):
                return "ENTER"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render_ui(store: RigPackStore, state: UiState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )

    tabs = ["[1] AUTO-DETECT", "[2] PROFILES", "[3] CLOUD & DIFF"]
    hdr = Text()
    hdr.append(" RIGPACK // CLOUD-AUTO ", style=f"bold {FG} on {ACCENT}")
    hdr.append("   ")
    for idx, label in enumerate(tabs):
        if idx == state.tab:
            hdr.append(f" {label} ", style=f"bold {FG} on {SURFACE}")
        else:
            hdr.append(f" {label} ", style=f"bold {MUTED}")
        hdr.append("  ")

    layout["header"].update(Panel(hdr, border_style=ACCENT, style=f"on {BG}"))

    detected = detect_targets()
    profiles = store.list_profiles()

    if state.tab == 0:
        max_idx = max(0, len(detected) - 1)
        state.cursor = min(state.cursor, max_idx)

        tbl = Table(
            title=f"AUTO-DETECTED GAMES & DEV APPS ({len(detected)})",
            border_style=BORDER_DIM,
            header_style=f"bold {ACCENT}",
            expand=True,
        )
        tbl.add_column("SEL", width=4)
        tbl.add_column("TYPE", width=7, style=f"bold {ACCENT}")
        tbl.add_column("TARGET", style=f"bold {FG}", width=34)
        tbl.add_column("PATHS FOUND", style=MUTED)

        for i, d in enumerate(detected):
            marker = "▶" if i == state.cursor else " "
            row_style = f"bold {FG} on {SURFACE}" if i == state.cursor else ""
            paths_preview = " | ".join(d.detected_paths[:2])
            if len(d.detected_paths) > 2:
                paths_preview += f" (+{len(d.detected_paths) - 2})"
            tbl.add_row(
                Text(marker, style=f"bold {ACCENT}"),
                d.category,
                d.display_name,
                paths_preview,
                style=row_style,
            )

        layout["main"].update(Panel(tbl, border_style=ACCENT, style=f"on {BG}", padding=(1, 1)))

    elif state.tab == 1:
        max_idx = max(0, len(profiles) - 1)
        state.cursor = min(state.cursor, max_idx)

        tbl = Table(
            title=f"REGISTERED PROFILES ({len(profiles)})",
            border_style=BORDER_DIM,
            header_style=f"bold {ACCENT}",
            expand=True,
        )
        tbl.add_column("SEL", width=4)
        tbl.add_column("PROFILE", width=18, style=f"bold {FG}")
        tbl.add_column("CAT", width=8, style=f"bold {ACCENT}")
        tbl.add_column("SNAPS", width=7, style=FG)
        tbl.add_column("TARGETS", style=MUTED)

        for i, p in enumerate(profiles):
            marker = "▶" if i == state.cursor else " "
            row_style = f"bold {FG} on {SURFACE}" if i == state.cursor else ""
            snaps = store.list_snapshots(p.name)
            t_preview = " | ".join(p.targets[:2])
            if len(p.targets) > 2:
                t_preview += f" (+{len(p.targets) - 2})"
            tbl.add_row(
                Text(marker, style=f"bold {ACCENT}"),
                p.name,
                p.category,
                str(len(snaps)),
                t_preview,
                style=row_style,
            )

        layout["main"].update(Panel(tbl, border_style=ACCENT, style=f"on {BG}", padding=(1, 1)))

    else:
        max_idx = max(0, len(profiles) - 1)
        state.cursor = min(state.cursor, max_idx)
        detail = Text()
        if not profiles:
            detail.append("No profiles registered yet. Switch to [1] AUTO-DETECT and press [A].\n", style=MUTED)
        else:
            p = profiles[state.cursor]
            snaps = store.list_snapshots(p.name)
            detail.append(f"PROFILE: {p.name} ({p.category})\n\n", style=f"bold {ACCENT}")
            detail.append(f"SNAPSHOTS ({len(snaps)}):\n", style=f"bold {FG}")
            for s in snaps[:6]:
                c_txt = f"  -> {s['cloud_url']}" if s.get("cloud_url") else "  [local-only]"
                detail.append(f"  • {s['snapshot_id']}  ({s['file_count']} files){c_txt}\n", style=FG)
            if not snaps:
                detail.append("  none yet — press [S] to snapshot & push to cloud\n", style=MUTED)
            else:
                detail.append("\nDRIFT VS LATEST SNAPSHOT:\n", style=f"bold {FG}")
                try:
                    diff = store.diff(p.name)
                    for bucket, col in [("modified", ACCENT), ("added", FG), ("missing", MUTED)]:
                        items = diff[bucket]
                        detail.append(f"  {bucket.upper()} ({len(items)}): ", style=f"bold {col}")
                        detail.append(", ".join(items[:5]) + (" ..." if len(items) > 5 else "") + "\n", style=MUTED)
                except Exception as exc:
                    detail.append(f"  diff unavailable: {exc}\n", style=MUTED)

        layout["main"].update(
            Panel(
                detail,
                title=f"[bold {ACCENT}]CLOUD BUNDLES & DRIFT INSPECTOR[/bold {ACCENT}]",
                border_style=ACCENT,
                style=f"on {BG}",
                padding=(1, 2),
            )
        )

    ft = Text()
    ft.append(" STATUS ", style=f"bold {FG} on {ACCENT}")
    ft.append(f"  {state.status_msg}", style=f"bold {FG}")
    layout["footer"].update(Panel(ft, border_style=ACCENT, style=f"on {BG}"))
    return layout


def run_tui(store: RigPackStore) -> int:
    if not sys.stdin.isatty():
        print("Interactive TUI requires a TTY terminal. Use CLI subcommands (e.g. `rigpack scan`).")
        return 1

    state = UiState()
    console = Console(style=f"on {BG}")

    try:
        with Live(_render_ui(store, state), console=console, screen=True, auto_refresh=False) as live:
            while True:
                live.update(_render_ui(store, state), refresh=True)
                key = _read_key()

                if key in ("q", "Q", "ESC"):
                    return 0
                if key == "1":
                    state.tab = 0
                    state.cursor = 0
                elif key == "2":
                    state.tab = 1
                    state.cursor = 0
                elif key == "3":
                    state.tab = 2
                    state.cursor = 0
                elif key == "TAB":
                    state.tab = (state.tab + 1) % 3
                    state.cursor = 0
                elif key == "SHIFT_TAB":
                    state.tab = (state.tab - 1) % 3
                    state.cursor = 0
                elif key in ("j", "J", "DOWN"):
                    state.cursor += 1
                elif key in ("k", "K", "UP"):
                    state.cursor = max(0, state.cursor - 1)
                elif key in ("a", "A") and state.tab == 0:
                    detected = detect_targets()
                    if detected and state.cursor < len(detected):
                        d = detected[state.cursor]
                        entry = store.add_profile(d.key, d.detected_paths, category=d.category, ignore=d.ignore)
                        state.status_msg = f"REGISTERED PROFILE: {entry.name} ({len(entry.targets)} path(s))"
                elif key in ("s", "S"):
                    profiles = store.list_profiles()
                    if profiles and state.cursor < len(profiles):
                        p = profiles[state.cursor]
                        try:
                            rec = store.snapshot(p.name, push_cloud=True)
                            url_info = f" -> {rec.cloud_url}" if rec.cloud_url else ""
                            state.status_msg = f"CLOUD SNAPSHOT SAVED: {p.name} ({rec.snapshot_id}){url_info}"
                        except Exception as exc:
                            rec = store.snapshot(p.name, push_cloud=False)
                            state.status_msg = f"LOCAL SNAP SAVED ({rec.snapshot_id}); cloud err: {exc}"
                elif key in ("r", "R"):
                    profiles = store.list_profiles()
                    if profiles and state.cursor < len(profiles):
                        p = profiles[state.cursor]
                        try:
                            sid, count = store.restore(p.name)
                            state.status_msg = f"RESTORED {p.name} from {sid} ({count} file(s))"
                        except Exception as exc:
                            state.status_msg = f"RESTORE FAILED: {exc}"
    except KeyboardInterrupt:
        return 0
