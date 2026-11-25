"""Command line: python -m vault_dashboard --vault PATH [--port 8767] [--host 127.0.0.1] [--config FILE]."""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .config import load_config
from .data import Vault
from .server import make_server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vault-dashboard", description="Local, read-only dashboard for a Markdown vault.")
    ap.add_argument("--vault", required=True, help="path to the vault (a folder of Markdown files)")
    ap.add_argument("--config", help="TOML config (default: <vault>/dashboard.toml if it exists)")
    ap.add_argument("--host", help="bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, help="port (default 8767)")
    ap.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
    ap.add_argument("--version", action="version", version=f"vault-dashboard {__version__}")
    a = ap.parse_args(argv)

    root = Path(a.vault).expanduser()
    if not root.is_dir():
        print(f"vault-dashboard: not a folder: {root}", file=sys.stderr)
        return 2
    cfg_path = Path(a.config).expanduser() if a.config else (
        Path(os.environ["VAULT_DASHBOARD_CONFIG"]) if os.environ.get("VAULT_DASHBOARD_CONFIG")
        else (root / "dashboard.toml" if (root / "dashboard.toml").is_file() else None))
    try:
        cfg = load_config(cfg_path)
    except (OSError, ValueError) as e:  # tomllib.TOMLDecodeError is a ValueError
        print(f"vault-dashboard: cannot read config {cfg_path}: {e}", file=sys.stderr)
        return 2

    host = a.host or cfg["dashboard"]["host"]
    port = a.port or cfg["dashboard"]["port"]
    try:
        srv = make_server(Vault(root, cfg), host, port)
    except OSError as e:
        print(f"vault-dashboard: cannot listen on {host}:{port}: {e}", file=sys.stderr)
        return 1
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{shown}:{port}"
    print(f"vault-dashboard {__version__}: {url}  (read-only, Ctrl+C to stop)")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("warning: listening beyond localhost; anyone who can reach this port can read your notes", file=sys.stderr)
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
