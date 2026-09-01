#!/usr/bin/env python3
"""
LigtasPH GUI Launcher — one-click open for Flask.
Usage: python run_gui.py  (or double-click)
- Auto init-db + seed if instance/ligtas.sqlite missing
- Opens browser to http://127.0.0.1:5000
- No secrets committed; reads .env via python-dotenv
"""
import os
import pathlib
import subprocess
import sys
import threading
import time
import webbrowser

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"

# Candidate venv locations (checked in order)
VENV_CANDIDATES = [
    pathlib.Path("./.venv"),
    pathlib.Path("./venv"),
    pathlib.Path("/tmp/ligtas_venv"),
    pathlib.Path("./env"),
]

def _venv_python(venv_path: pathlib.Path):
    # Unix venv python
    p = venv_path / "bin" / "python"
    if p.exists():
        return str(p)
    # Windows
    p = venv_path / "Scripts" / "python.exe"
    if p.exists():
        return str(p)
    return None

def ensure_venv():
    """
    Ensure we run inside a venv with Flask installed.
    - If already inside a venv (sys.prefix != sys.base_prefix) -> ok.
    - Else, try to re-exec with first valid venv python found.
    - Else, guide user to create venv.
    """
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        # check Flask installed
        try:
            import flask  # noqa
            return True
        except ImportError:
            print("[run_gui] venv active but Flask missing — installing requirements...", file=sys.stderr)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            return True

    # not in venv — try to find one and re-exec
    for cand in VENV_CANDIDATES:
        py = _venv_python(cand)
        if py:
            # avoid infinite loop: don't re-exec if already that python
            if pathlib.Path(py).resolve() == pathlib.Path(sys.executable).resolve():
                return True
            print(f"[run_gui] Found venv at {cand} → re-executing with {py}")
            # re-exec preserves args
            os.execv(py, [py] + sys.argv)

    # no venv found — auto-create ./venv if possible
    venv_path = pathlib.Path("./venv")
    if not venv_path.exists():
        print("[run_gui] No venv found — creating ./venv (Python 3.11+ required)...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
            py = _venv_python(venv_path)
            print(f"[run_gui] Created {venv_path}. Installing dependencies...")
            subprocess.check_call([py, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
            print(f"[run_gui] Setup done. Re-executing with {py}...")
            os.execv(py, [py] + sys.argv)
        except Exception as e:
            print(f"[run_gui] Auto-venv failed: {e}", file=sys.stderr)
            print("[run_gui] Fix manually:", file=sys.stderr)
            print("  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt", file=sys.stderr)
            return False
    else:
        print(f"[run_gui] venv exists at {venv_path} but not active.", file=sys.stderr)
        print(f"[run_gui] Activate it:", file=sys.stderr)
        print("  source venv/bin/activate  # Windows: venv\\Scripts\\activate", file=sys.stderr)
        print("  pip install -r requirements.txt", file=sys.stderr)
        return False
    return False

def ensure_db():
    db_path = pathlib.Path("instance/ligtas.sqlite")
    if db_path.exists():
        return
    print("[run_gui] DB not found — initializing and seeding...")
    try:
        from app import create_app
        from utils.db import init_db
        from utils.seed import seed_db
        app = create_app()
        with app.app_context():
            init_db()
            seed_db()
        print("[run_gui] DB ready at", db_path)
    except Exception as e:
        print(f"[run_gui] DB init failed: {e}", file=sys.stderr)

def open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open(URL)
        print(f"[run_gui] Opened browser to {URL}")
    except Exception as e:
        print(f"[run_gui] Could not open browser: {e}. Visit {URL} manually.")

def main():
    # 1. Ensure venv + deps before anything else (auto-creates/re-execs if needed)
    if not ensure_venv():
        # if we didn't re-exec, still try to continue with system python
        try:
            import flask  # noqa
        except ImportError:
            print("[run_gui] Flask not installed. Run: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)

    print(f"[run_gui] Using Python: {sys.executable}")
    print(f"[run_gui] venv active: {sys.prefix != sys.base_prefix} (prefix={sys.prefix})")

    ensure_db()
    # start browser thread
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    try:
        from app import app
        print(f"[run_gui] Starting LigtasPH GUI at {URL} — Ctrl+C to stop")
        # use_reloader False so browser doesn't open twice
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    except ImportError as e:
        print(f"[run_gui] Import failed: {e}. Did you activate venv and pip install -r requirements.txt?", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
