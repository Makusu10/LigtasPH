#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).parent.resolve()
DEFAULT_PORT = 3000
DEFAULT_URL = f"http://localhost:{DEFAULT_PORT}"
HEALTH_ENDPOINT = f"/api/centers"  # defined at server.ts:167
POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 45.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch LigtasPH GUI in browser")
    parser.add_argument("--no-server", action="store_true",
                        help="Do not start dev server; only open browser")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--url", type=str, default=None,
                        help="Full URL to open (overrides --port)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Start server but do not open browser (useful for CI)")
    return parser.parse_args()


def check_dependencies() -> None:
    """Verify Node and package manager are available."""
    if shutil.which("node") is None:
        print("ERROR: 'node' not found in PATH. Install Node.js 22+ first.", file=sys.stderr)
        sys.exit(1)
    # npm or bun — prefer npm if both exist (matches package-lock.json)
    has_npm = shutil.which("npm") is not None
    has_bun = shutil.which("bun") is not None
    if not has_npm and not has_bun:
        print("ERROR: neither 'npm' nor 'bun' found in PATH.", file=sys.stderr)
        sys.exit(1)


def is_server_up(url: str) -> bool:
    """Poll HEALTH_ENDPOINT to see if Express is already serving."""
    try:
        with urlopen(f"{url}{HEALTH_ENDPOINT}", timeout=2) as resp:
            return resp.status == 200
    except URLError:
        return False
    except Exception:
        return False


def start_dev_server() -> subprocess.Popen:
    """Start `npm run dev` (tsx server.ts) as a child process."""
    # Choose package manager: prefer npm, fallback to bun
    if shutil.which("npm"):
        cmd = ["npm", "run", "dev"]
    else:
        cmd = ["bun", "run", "dev"]

    print(f"Starting dev server: {' '.join(cmd)} (cwd={PROJECT_ROOT})")
    # Use project root as cwd so server.ts resolves correctly
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return proc


def wait_for_server(url: str, timeout: float = POLL_TIMEOUT_SEC) -> bool:
    """Block until HEALTH_ENDPOINT returns 200 or timeout expires."""
    print(f"Waiting for server at {url}{HEALTH_ENDPOINT} (timeout {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_server_up(url):
            print("Server is ready.")
            return True
        time.sleep(POLL_INTERVAL_SEC)
    return False


def main() -> None:
    args = parse_args()
    url = args.url if args.url else f"http://localhost:{args.port}"

    check_dependencies()

    server_proc: subprocess.Popen | None = None

    try:
        if not args.no_server:
            # If server already up, reuse it instead of spawning a second one
            if is_server_up(url):
                print(f"Server already running at {url} — reusing existing instance.")
            else:
                server_proc = start_dev_server()
                ready = wait_for_server(url)
                if not ready:
                    print(f"Timed out waiting for {url}. Check terminal output above.", file=sys.stderr)
                    if server_proc and server_proc.poll() is None:
                        print("Server process is still running but not responding on /api/centers.", file=sys.stderr)
                    # Still try to open browser — Vite may still be compiling
                # Give Vite a moment to finish HMR setup
                time.sleep(1.0)
        else:
            print(f"--no-server: skipping server start, will open {url} directly.")

        if not args.no_browser:
            print(f"Opening browser at {url}")
            # webbrowser.open is cross-platform (uses `xdg-open` on Linux, `open` on macOS, start on Windows)
            opened = webbrowser.open(url)
            if not opened:
                print(f"Could not open browser automatically. Please navigate to {url} manually.")
            else:
                print(f"Browser opened. If geolocation is denied, map falls back to Marikina default (server.ts:93).")
                print(f"Admin login: admin / password (seeded at server.ts:106)")
        else:
            print(f"--no-browser: not opening browser. Server at {url}")

        if server_proc:
            print("\nDev server is running. Press Ctrl+C to stop.")
            # Stream server logs to console until interrupted
            try:
                assert server_proc.stdout is not None
                for line in server_proc.stdout:
                    print(line, end="")
                    # Also detect readiness from stdout as fallback
                    if is_server_up(url):
                        pass
            except KeyboardInterrupt:
                pass
        else:
            if not args.no_server:
                # We reused existing server — nothing to stream; just exit after opening browser
                print("Done. Existing server will keep running. Stop it with: pkill -f \"tsx server.ts\"")
            else:
                print("Done.")

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")

    finally:
        if server_proc and server_proc.poll() is None:
            print("Stopping dev server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("Server stopped.")


if __name__ == "__main__":
    main()
