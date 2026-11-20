from __future__ import annotations

import fnmatch
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KnownTargetSpec:
    key: str
    display_name: str
    category: str  # "GAME" or "DEV"
    aliases: list[str]
    windows_paths: list[str]
    linux_paths: list[str]
    ignore: list[str] = field(default_factory=list)


@dataclass
class DetectedTarget:
    key: str
    display_name: str
    category: str
    detected_paths: list[str]
    ignore: list[str]


DEFAULT_IGNORES = [
    "__pycache__",
    ".git",
    "node_modules",
    "cache",
    "Cache",
    "GPUCache",
    "Code Cache",
    "logs",
    "crash-reports",
    "*.tmp",
    "*.log",
    "*.bak",
]


BUILTIN_TARGETS: list[KnownTargetSpec] = [
    KnownTargetSpec(
        key="minecraft",
        display_name="Minecraft (Java / Prism / Modrinth)",
        category="GAME",
        aliases=["mc", "minecraft", "fabric", "prism", "modrinth"],
        windows_paths=[
            "%APPDATA%/.minecraft/options.txt",
            "%APPDATA%/.minecraft/config",
            "%APPDATA%/.minecraft/shaderpacks",
            "%USERPROFILE%/AppData/Roaming/PrismLauncher/instances",
            "%USERPROFILE%/AppData/Roaming/com.modrinth.theseus/profiles",
        ],
        linux_paths=[
            "~/.minecraft/options.txt",
            "~/.minecraft/config",
            "~/.minecraft/shaderpacks",
            "~/.local/share/PrismLauncher/instances",
            "~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances",
        ],
        ignore=DEFAULT_IGNORES + ["assets", "libraries", "versions", "saves/*/region"],
    ),
    KnownTargetSpec(
        key="roblox",
        display_name="Roblox Studio & Client Configs",
        category="GAME",
        aliases=["rblx", "roblox", "roblox studio", "studio"],
        windows_paths=[
            "%LOCALAPPDATA%/Roblox/GlobalBasicSettings_13.xml",
            "%LOCALAPPDATA%/Roblox/RobloxStudioSettings.xml",
            "%LOCALAPPDATA%/Roblox/ClientSettings",
            "%LOCALAPPDATA%/Roblox/Plugins",
        ],
        linux_paths=[
            "~/.local/share/sober/home/.local/share/Roblox",
            "~/.wine/drive_c/users/$USER/AppData/Local/Roblox",
        ],
        ignore=DEFAULT_IGNORES + ["Versions", "Logs", "Temp", "Downloaded"],
    ),
    KnownTargetSpec(
        key="steam-games",
        display_name="Steam Library Configs & Userdata",
        category="GAME",
        aliases=["steam", "valve", "steamuserdata"],
        windows_paths=[
            "C:/Program Files (x86)/Steam/config",
            "C:/Program Files (x86)/Steam/userdata",
            "C:/Program Files/Steam/config",
        ],
        linux_paths=[
            "~/.local/share/Steam/config",
            "~/.steam/steam/config",
            "~/.local/share/Steam/userdata",
        ],
        ignore=DEFAULT_IGNORES + ["depotcache", "steamapps", "appcache"],
    ),
    KnownTargetSpec(
        key="retroarch",
        display_name="RetroArch Emulation Configs",
        category="GAME",
        aliases=["retroarch", "emu", "emulator"],
        windows_paths=[
            "%APPDATA%/RetroArch/retroarch.cfg",
            "%APPDATA%/RetroArch/config",
            "%APPDATA%/RetroArch/saves",
        ],
        linux_paths=[
            "~/.config/retroarch/retroarch.cfg",
            "~/.config/retroarch/config",
            "~/.local/share/retroarch/saves",
        ],
    ),
    KnownTargetSpec(
        key="terraria",
        display_name="Terraria & tModLoader",
        category="GAME",
        aliases=["terraria", "tmodloader"],
        windows_paths=[
            "%USERPROFILE%/Documents/My Games/Terraria/config.json",
            "%USERPROFILE%/Documents/My Games/Terraria/Players",
            "%USERPROFILE%/Documents/My Games/Terraria/tModLoader",
        ],
        linux_paths=[
            "~/.local/share/Terraria/config.json",
            "~/.local/share/Terraria/Players",
            "~/.local/share/Terraria/tModLoader",
        ],
    ),
    KnownTargetSpec(
        key="hyprland",
        display_name="Hyprland (hyprland.lua / hyprland.conf)",
        category="DEV",
        aliases=["hypr", "hyprland", "hyprlua", "wayland"],
        windows_paths=[],
        linux_paths=[
            "~/.config/hypr/hyprland.lua",
            "~/.config/hypr/hyprland.conf",
            "~/.config/hypr/hyprpaper.conf",
        ],
    ),
    KnownTargetSpec(
        key="terminal-shells",
        display_name="Shells & Prompts (Fish / Bash / Zsh / Starship)",
        category="DEV",
        aliases=["shell", "fish", "bash", "zsh", "starship", "terminal"],
        windows_paths=[
            "%USERPROFILE%/.config/starship.toml",
            "%USERPROFILE%/Documents/PowerShell/Microsoft.PowerShell_profile.ps1",
        ],
        linux_paths=[
            "~/.config/fish/config.fish",
            "~/.config/fish/functions",
            "~/.zshrc",
            "~/.bashrc",
            "~/.config/starship.toml",
            "~/.config/kitty/kitty.conf",
            "~/.config/alacritty/alacritty.toml",
        ],
    ),
    KnownTargetSpec(
        key="neovim-editors",
        display_name="Neovim & Terminal Editors",
        category="DEV",
        aliases=["nvim", "neovim", "vim", "editor", "helix"],
        windows_paths=[
            "%LOCALAPPDATA%/nvim",
            "%USERPROFILE%/.config/helix",
        ],
        linux_paths=[
            "~/.config/nvim",
            "~/.config/helix",
            "~/.config/micro",
        ],
        ignore=DEFAULT_IGNORES + ["lazy-lock.json", "plugin", "spell"],
    ),
    KnownTargetSpec(
        key="git-ssh",
        display_name="Git & SSH Configs",
        category="DEV",
        aliases=["git", "gitconfig", "ssh"],
        windows_paths=[
            "%USERPROFILE%/.gitconfig",
            "%USERPROFILE%/.ssh/config",
        ],
        linux_paths=[
            "~/.gitconfig",
            "~/.config/git/config",
            "~/.ssh/config",
        ],
    ),
    KnownTargetSpec(
        key="ai-cli-tools",
        display_name="AI CLI & Local Router Configs",
        category="DEV",
        aliases=["ai", "llm", "opencode", "claude", "lmstudio", "ollama", "router"],
        windows_paths=[
            "%USERPROFILE%/.config/opencode",
            "%USERPROFILE%/.claude/settings.json",
            "%USERPROFILE%/.lmstudio",
        ],
        linux_paths=[
            "~/.config/opencode",
            "~/.claude/settings.json",
            "~/.config/ollama",
            "~/.lmstudio",
        ],
    ),
]


def _expand_candidates(raw_patterns: list[str]) -> list[Path]:
    expanded: list[Path] = []
    user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    for raw in raw_patterns:
        s = raw.replace("$USER", user)
        s = os.path.expandvars(os.path.expanduser(s))
        p = Path(s)
        if p.exists():
            expanded.append(p.resolve())
    seen: set[str] = set()
    uniq: list[Path] = []
    for item in expanded:
        key = str(item)
        if key not in seen:
            seen.add(key)
            uniq.append(item)
    return uniq


def detect_targets(query: str | None = None, category: str | None = None) -> list[DetectedTarget]:
    is_windows = platform.system().lower().startswith("win")
    q = (query or "").strip().lower()
    cat = (category or "").strip().upper() or None

    found: list[DetectedTarget] = []
    for spec in BUILTIN_TARGETS:
        if cat and spec.category != cat:
            continue
        if q:
            haystack = [spec.key.lower(), spec.display_name.lower()] + [a.lower() for a in spec.aliases]
            matched = any(q == h or q in h or fnmatch.fnmatch(h, q) for h in haystack)
            if not matched:
                continue

        candidates = spec.windows_paths if is_windows else spec.linux_paths
        alt_candidates = spec.linux_paths if is_windows else spec.windows_paths
        existing = _expand_candidates(candidates + alt_candidates)
        if existing:
            found.append(
                DetectedTarget(
                    key=spec.key,
                    display_name=spec.display_name,
                    category=spec.category,
                    detected_paths=[str(p) for p in existing],
                    ignore=list(dict.fromkeys(spec.ignore + DEFAULT_IGNORES)),
                )
            )
    return found


def all_known_specs(category: str | None = None) -> list[KnownTargetSpec]:
    cat = (category or "").strip().upper() or None
    if not cat:
        return list(BUILTIN_TARGETS)
    return [s for s in BUILTIN_TARGETS if s.category == cat]
