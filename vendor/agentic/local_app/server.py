"""Run a loopback-only desk: python -m local_app.server --open."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import uuid
from urllib.parse import parse_qs, urlsplit
import webbrowser

from .engine import DEFAULT_MODEL, DeskError, ROLES, ROOT, market_snapshot, run_agent, utc_now

STATIC = Path(__file__).parent / "static"


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, seat TEXT NOT NULL,
                    created_at TEXT NOT NULL, details TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self):
        identity = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES (?, ?, ?)", (identity, "New conversation", utc_now()))
        return identity

    def conversations(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT 100")]

    def messages(self, identity):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (identity,)).fetchone():
                raise DeskError("Conversation not found.")
            rows = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (identity,))
            return [{**dict(row), "details": json.loads(row["details"])} for row in rows]

    def save_turn(self, identity, message, seat, answer):
        with self.connect() as db:
            first = not db.execute("SELECT 1 FROM messages WHERE conversation_id=? LIMIT 1", (identity,)).fetchone()
            for role, text, details in (("user", message, {}), ("assistant", answer["content"], answer)):
                db.execute("INSERT INTO messages (conversation_id,role,content,seat,created_at,details) VALUES (?,?,?,?,?,?)",
                           (identity, role, text, seat, utc_now(), json.dumps(details)))
            if first:
                db.execute("UPDATE conversations SET title=? WHERE id=?", (message[:65], identity))


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store):
        super().__init__(address, Handler)
        self.store = store
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self.csrf_token = secrets.token_urlsafe(32)
        self.turn_lock = threading.Lock()
        self.settings_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: DeskServer

    def log_message(self, format, *args):
        pass  # No request bodies, prompts, provider errors or keys in access logs.

    def send(self, status, data, content_type="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionError, OSError):
            pass

    def trusted_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def do_GET(self):
        if not self.trusted_host():
            return self.send(403, {"error": "Use the local app URL."})
        route = urlsplit(self.path)
        try:
            if route.path == "/api/status":
                with self.server.settings_lock:
                    return self.send(200, {"provider": "OpenAI", "model": self.server.model,
                        "configured": bool(self.server.api_key), "mode": "research",
                        "roles": ROLES, "csrf_token": self.server.csrf_token,
                        "storage": str(self.server.store.path), "exchange_writes": False,
                        "radar_integration": True})
            if route.path == "/api/conversations":
                return self.send(200, self.server.store.conversations())
            if route.path == "/api/messages":
                return self.send(200, self.server.store.messages(parse_qs(route.query).get("id", [""])[0]))
            if route.path == "/api/market":
                coin = parse_qs(route.query).get("coin", ["ETH"])[0]
                return self.send(200, market_snapshot(coin))
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if route.path in files:
                name, mime = files[route.path]
                return self.send(200, (STATIC / name).read_bytes(), mime)
            return self.send(404, {"error": "Not found."})
        except DeskError as exc:
            return self.send(400, {"error": str(exc)})
        except Exception:
            return self.send(500, {"error": "The local request failed. Check the app and retry."})

    def do_POST(self):
        origin = self.headers.get("Origin")
        allowed_origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        token = self.headers.get("X-Desk-Token", "")
        if not self.trusted_host() or (origin and origin not in allowed_origins) or not hmac.compare_digest(token, self.server.csrf_token):
            return self.send(403, {"error": "Reload the local app before making changes."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768 or self.headers.get_content_type() != "application/json":
                return self.send(400, {"error": "Expected a JSON request under 32 KB."})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise DeskError("Expected a JSON object.")
            if self.path == "/api/settings":
                model = data.get("model", DEFAULT_MODEL)
                key = data.get("api_key", "")
                if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9._:-]{1,100}", model):
                    raise DeskError("Enter a valid OpenAI model ID.")
                if not isinstance(key, str) or len(key) > 512 or any(c.isspace() for c in key):
                    raise DeskError("Enter a valid OpenAI API key.")
                with self.server.settings_lock:
                    if data.get("clear_key") is True:
                        self.server.api_key = ""
                    elif key:
                        self.server.api_key = key
                    self.server.model = model
                return self.send(200, {"ok": True})
            if self.path == "/api/conversations":
                return self.send(201, {"id": self.server.store.create()})
            if self.path == "/api/chat":
                message, identity, role = data.get("message"), data.get("conversation_id"), data.get("role", "desk-lead")
                if not isinstance(message, str) or not message.strip() or len(message) > 8000:
                    raise DeskError("Write a message of 1 to 8,000 characters.")
                if re.search(r"\bsk-[A-Za-z0-9_-]{16,}", message):
                    raise DeskError("Use Settings for your OpenAI key. Do not put secrets in chat.")
                if not isinstance(identity, str) or not isinstance(role, str) or role not in ROLES:
                    raise DeskError("Choose a conversation and desk role.")
                if not self.server.turn_lock.acquire(blocking=False):
                    return self.send(409, {"error": "The desk is finishing another request. Please wait."})
                try:
                    history = self.server.store.messages(identity)
                    with self.server.settings_lock:
                        key, model = self.server.api_key, self.server.model
                    answer = run_agent(key, model, role, history, message.strip())
                    self.server.store.save_turn(identity, message.strip(), role, answer)
                    return self.send(200, answer)
                finally:
                    self.server.turn_lock.release()
            return self.send(404, {"error": "Not found."})
        except (ValueError, TypeError):
            return self.send(400, {"error": "Invalid JSON request."})
        except DeskError as exc:
            return self.send(400, {"error": str(exc)})
        except Exception:
            return self.send(500, {"error": "The local request failed. Retry or restart the app."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the app in your browser")
    default_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "AgenticTradingDesk"
    parser.add_argument("--data-dir", type=Path, default=default_data)
    args = parser.parse_args()
    try:
        server = DeskServer(("127.0.0.1", args.port), Store(args.data_dir / "desk.sqlite3"))
    except OSError:
        parser.exit(1, f"Cannot start on port {args.port}. Try --port 8766.\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Agentic desk: {url}\nProvider: OpenAI | Mode: research | Exchange execution: disabled\nData: {server.store.path}\nPress Ctrl+C to stop.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
