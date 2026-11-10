"""Launch the local research integration. No exchange credentials are passed to the agent."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def read_json(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=2) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desk-path", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="verify startup, then stop the services started by this run")
    args = parser.parse_args()
    config = ROOT / "desk.integration.json"
    source = args.desk_path
    if source is None and config.exists():
        source = Path(json.loads(config.read_text(encoding="utf-8"))["desk_path"])
    if source is None:
        source = ROOT / "vendor" / "agentic"
    if source is None or not (source / "local_app" / "server.py").is_file():
        parser.exit(1, 'Supply the Agentic source checkout: python scripts/start_integrated_desk.py --desk-path "C:/path/to/agentic"\n')
    api_python = ROOT / "apps" / "api" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not api_python.exists():
        api_python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not api_python.exists():
        parser.exit(1, "Create Radar's Python virtual environment and install apps/api/requirements.txt first.\n")
    node = shutil.which("node")
    next_bin = ROOT / "apps" / "web" / "node_modules" / "next" / "dist" / "bin" / "next"
    if not node or not next_bin.exists():
        parser.exit(1, "Install Node.js and run npm install in apps/web first.\n")
    if listening(8010) or listening(3000):
        parser.exit(1, "Port 8010 or 3000 is already in use. Stop the existing Radar development server before using this launcher. No existing service was changed.\n")
    reuse_desk = listening(8765)
    if reuse_desk:
        try:
            status = read_json("http://127.0.0.1:8765/api/status")
            if status.get("exchange_writes") is not False or not status.get("radar_integration"):
                raise ValueError("Old or unexpected desk service")
        except Exception:
            parser.exit(1, "Port 8765 has an old or unexpected service. Stop it and restart this launcher.\n")
    children = []
    files = []
    runtime = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "AgenticTradingDesk"
    runtime.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def launch(name, command, cwd, env):
        log = runtime / f"{name}-{stamp}.log"
        output = log.open("w", encoding="utf-8")
        files.append(output)
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, creationflags=flags)
        children.append(process)
        print(f"Started {name} (PID {process.pid}). Log: {log}", flush=True)

    # The model process receives only its provider key; exchange credentials and custom
    # provider URLs are not inherited from Radar configuration or the parent environment.
    agent_env = {k: v for k, v in os.environ.items()
                 if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "OPENAI_API_KEY", "OPENAI_MODEL", "SSL_CERT_FILE"}}
    agent_env["AGENTIC_RADAR_URL"] = "http://127.0.0.1:8010"
    agent_env["PYTHONIOENCODING"] = "utf-8"
    api_env = dict(os.environ)
    # This launcher always starts a research session, regardless of any local .env flags.
    for name in ("PRIVATE_API", "TRADING", "BINANCE", "BINANCE_TRADING", "EXIT_AUTOMATION", "WEBSOCKET_MONITORING"):
        api_env[f"FMR_ENABLE_{name}"] = "false"
    api_env.update(FMR_RUN_INITIAL_SCAN="false", FMR_RUN_INITIAL_MARKET_INTELLIGENCE="false",
                   FMR_DESK_BASE_URL="http://127.0.0.1:8765",
                   FMR_ALLOW_ORIGINS="http://localhost:3000,http://127.0.0.1:3000",
                   PYTHONIOENCODING="utf-8")
    web_env = dict(os.environ)
    web_env.update(API_BASE_URL="http://127.0.0.1:8010", NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8010")
    try:
        if not reuse_desk:
            launch("desk", [sys.executable, "-m", "local_app.server"], source.resolve(), agent_env)
        launch("radar-api", [str(api_python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010"], ROOT / "apps/api", api_env)
        launch("radar-web", [node, str(next_bin), "dev", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "apps/web", web_env)
        print("Research mode: private sync, exchange execution, and managed exits are disabled.\nWaiting for the workspace...", flush=True)
        for _ in range(120):
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited. See the log paths above.")
            try:
                status = read_json("http://127.0.0.1:8010/api/desk/status")
                if status.get("radar_integration") and listening(3000):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Startup timed out. See the service logs above.")
        print("Ready: http://127.0.0.1:3000/desk\nKeep this window open. Ctrl+C stops the services started by this launcher.", flush=True)
        if args.check:
            return 0
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:3000/desk")
        while all(child.poll() is None for child in children):
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping the integration...", flush=True)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                if os.name == "nt":
                    # Windows venv redirectors and Next can spawn child servers.
                    # Stop only this launcher's still-running child process tree.
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for output in files:
            output.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
