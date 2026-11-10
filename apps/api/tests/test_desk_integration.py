"""Offline browser/API/evidence bridge journeys. Never starts Radar's live lifespan."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.routes.desk import router
from app.services.desk_bridge import DeskBridge


class AgenticFixture(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_args):
        pass

    def reply(self, code, value):
        payload = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        type(self).calls.append(("GET", self.path))
        if self.path == "/api/status":
            return self.reply(200, {"configured": False, "csrf_token": "fixture-token", "exchange_writes": False, "radar_integration": True})
        self.reply(200, [])

    def do_POST(self):
        type(self).calls.append(("POST", self.path))
        if self.headers.get("X-Desk-Token") != "fixture-token":
            return self.reply(403, {"error": "Invalid local token"})
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/chat":
            return self.reply(200, {"content": "Fixture research report", "received_role": data["role"], "traces": [], "usage": {"input_tokens": 1, "output_tokens": 1}})
        self.reply(201, {"id": "a" * 32})


class DeskIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + (Path(self.temp.name) / "fixture.db").as_posix(), connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.patch = patch("app.routes.desk.SessionLocal", self.sessions)
        self.patch.start()
        self.agentic = ThreadingHTTPServer(("127.0.0.1", 0), AgenticFixture)
        AgenticFixture.calls = []
        self.thread = threading.Thread(target=self.agentic.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.agentic.server_port}"
        app = FastAPI()
        app.state.settings = SimpleNamespace(desk_base_url=self.origin, allowed_origins=["http://localhost:3000"], market_data_source="fixture")
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.agentic.shutdown()
        self.agentic.server_close()
        self.thread.join()
        self.patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_read_only_status_and_mutation_authority(self):
        self.assertFalse(self.client.get('/api/desk/status').json()['exchange_writes'])
        self.assertEqual(self.client.post('/api/desk/conversations').status_code, 403)
        headers = {"X-Desk-Token": "fixture-token", "Origin": "https://untrusted.example"}
        self.assertEqual(self.client.post('/api/desk/conversations', headers=headers).status_code, 403)
        headers['Origin'] = 'http://localhost:3000'
        self.assertEqual(self.client.post('/api/desk/conversations', headers=headers).status_code, 201)
        headers['X-Desk-Token'] = 'wrong'
        self.assertEqual(self.client.post('/api/desk/conversations', headers=headers).status_code, 403)

    def test_chat_roundtrip_and_no_order_proxy(self):
        response = self.client.post('/api/desk/chat', headers={"X-Desk-Token": "fixture-token"}, json={
            "conversation_id": "a" * 32, "role": "market-analyst", "message": "Read the stored ETH observations."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['received_role'], 'market-analyst')
        self.assertEqual(self.client.post('/api/desk/trading/order', json={}).status_code, 404)
        self.assertEqual(self.client.get('/api/desk/messages?id=../secret').status_code, 422)
        self.assertFalse(any('/trading/' in path for _, path in AgenticFixture.calls))

    def test_missing_and_stale_evidence_preserve_venue(self):
        missing = self.client.get('/api/desk/evidence?symbol=ETH').json()
        self.assertEqual(missing['status'], 'unavailable')
        self.assertIsNone(missing['market'])
        when = datetime.now(timezone.utc) - timedelta(days=1)
        with self.sessions() as db:
            db.add(models.MarketSnapshot(symbol='ETH_USDT_PERP', price=2200, price_change_24h=1, volume_24h=10,
                quote_volume_24h=22000, high_24h=2300, low_24h=2100, open_interest=100, timestamp=when))
            db.commit()
        data = self.client.get('/api/desk/evidence?symbol=ETH_USDT_PERP').json()
        self.assertEqual(data['exchange'], 'pionex')
        self.assertEqual(data['market']['price'], 2200)
        self.assertEqual(data['market']['freshness'], 'stale_or_future')
        self.assertEqual(self.client.get('/api/desk/evidence?symbol=BTC').json()['status'], 'unavailable')
        self.assertEqual(self.client.get('/api/desk/evidence?symbol=xyz:TSLA').status_code, 422)

    def test_external_origins_and_unapproved_routes_are_rejected(self):
        for origin in ['https://example.com', 'http://127.0.0.1:8765/other', 'http://user:pass@localhost:8765', 'http://localhost:8765?path=/exchange']:
            with self.assertRaises(ValueError):
                DeskBridge(origin)
        import asyncio
        with self.assertRaises(HTTPException):
            asyncio.run(DeskBridge(self.origin).call('POST', 'trading/order', body={}))


if __name__ == '__main__':
    unittest.main()
