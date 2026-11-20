# rigpack

**rigpack** is a cross-platform snapshot, SHA-256 diff, rollback, and zero-setup cloud backup utility built for gamers and developers who want their game configurations, mod setups, and development environments protected without manual folder juggling.

---

## Introduction

Modern gaming and software development setups break easily. A single mod update, shader experiment, launcher patch, or dotfile edit can overwrite hours of fine-tuned settings—whether you are tuning graphics and keybinds in **Minecraft**, **Roblox**, **Steam** games, or **RetroArch**, or maintaining **Hyprland**, **Fish/Bash/Zsh**, **Kitty/Alacritty**, **Neovim/Helix**, **Git/SSH**, or local AI/router configs.

**rigpack** solves this by treating your game configs and developer environments like versioned snapshots:

* **Automatic Detection by Name:** Scans common Windows and Linux paths to discover installed games and developer tools automatically so you do not have to hunt down hidden directories by hand.
* **Timestamped Snapshots & Safe Rollbacks:** Captures clean snapshots while automatically skipping noisy cache, log, and temporary bloat, and creates a safety backup before restoring so you never lose current state accidentally.
* **SHA-256 Drift Detection (`diff`):** Compares live files against your latest snapshot to show exactly what changed, was added, or was removed before you overwrite anything.
* **Interactive Brutalist TUI & CLI:** Use the keyboard-driven terminal UI (`rigpack` / `rigpack ui`) to browse detected targets, inspect drift, and trigger actions visually, or run fast scripted commands from the CLI.
* **Zero-Config Cloud Bundles:** Packages snapshots into `.zip` bundles and uploads them automatically so you can recover or pull a setup without managing cloud consoles, buckets, or API keys yourself.

---

## How to Set Up Cloud Upload for Free

**rigpack** works out of the box with zero account registration or billing required:

1. **Default Zero-Setup Endpoint:** By default, `rigpack snap <name>` (or pressing `s` in the TUI) creates a snapshot archive and uploads it to the default free upload endpoint (`https://0x0.st`) with no API keys or dashboard configuration needed. Your uploaded bundle URLs are saved locally in `cloud_index.json`.
2. **Local-Only Mode (When You Want Offline Snapshots):** If you want to take a snapshot strictly on disk without uploading, run:
   ```bash
   rigpack snap <name> --local-only
   ```
3. **Custom or Free Self-Hosted / Alternative Endpoint:** You can point `rigpack` to a compatible upload endpoint via the `RIGPACK_CLOUD_URL` environment variable before running commands:
   * **Linux / macOS (bash / zsh):**
     ```bash
     export RIGPACK_CLOUD_URL="https://0x0.st"
     rigpack snap minecraft
     ```
   * **Fish shell:**
     ```fish
     set -gx RIGPACK_CLOUD_URL "https://0x0.st"
     rigpack snap minecraft
     ```
   * **Windows (PowerShell):**
     ```powershell
     $env:RIGPACK_CLOUD_URL = "https://0x0.st"
     rigpack snap minecraft
     ```
4. **Pulling & Pushing Bundles:**
   * Push an existing snapshot to the cloud:
     ```bash
     rigpack push <name>
     ```
   * Pull a snapshot bundle back down by profile name or direct URL:
     ```bash
     rigpack pull <name>
     rigpack pull <name> --url "https://your-bundle-url/snapshot.zip"
     ```

> **Practical Note on Free Upload Hosts:** Public/free ephemeral upload services can occasionally rate-limit requests, restrict large archives, or expire links over time. Keep local snapshots enabled for critical setups, and point `RIGPACK_CLOUD_URL` to your own durable endpoint if you need long-term retention.

---

## Installation

### Prerequisites
* **Python 3.10+**
* **Git** (if cloning from GitHub)

### Step-by-Step Install

1. **Clone or extract the repository and enter the project folder:**
   ```bash
   git clone https://github.com/nirbhontop/rigpack.git
   cd rigpack
   ```
   *(If you downloaded and extracted a `rigpack` ZIP archive instead, `cd` into the inner `rigpack` folder containing `pyproject.toml`.)*

2. **Create and activate a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   # Linux / macOS:
   source .venv/bin/activate
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Windows (Command Prompt):
   .venv\Scripts\activate.bat
   ```

3. **Install `rigpack`:**
   ```bash
   pip install -e .
   ```
   If you are upgrading an existing installation after code updates, force-reinstall the entrypoint cleanly:
   ```bash
   pip install --force-reinstall --no-deps .
   ```

4. **Verify the installation:**
   ```bash
   rigpack --help
   rigpack scan
   ```

### Basic Usage Overview

* **Launch the interactive TUI:**
  ```bash
  rigpack
  ```
* **Auto-detect games & dev configs and register them:**
  ```bash
  rigpack scan
  rigpack scan --register
  ```
* **Snapshot, inspect changes, and restore:**
  ```bash
  rigpack snap <name>
  rigpack diff <name>
  rigpack restore <name>
  ```

---

## License

MIT License

Copyright (c) 2026 Nirbhaya Shiwakoti

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.