from __future__ import annotations

import unittest

from app.services.pionex_client import PionexKline
from app.services.signal_engine import SignalEngine


def candles(direction: str = "up") -> list[PionexKline]:
    items: list[PionexKline] = []
    price = 100.0
    for index in range(60):
        delta = 0.4 if direction == "up" else -0.4
        open_price = price
        close = price + delta
        high = max(open_price, close) + 0.2
        low = min(open_price, close) - 0.2
        items.append(PionexKline(time=index, open=open_price, close=close, high=high, low=low, volume=100 + index))
        price = close
    return items


class SignalEngineTest(unittest.TestCase):
    def test_uptrend_produces_directional_signal(self) -> None:
        signal = SignalEngine().analyze("BTC_USDT_PERP", "15m", candles("up"))

        self.assertIn(signal.direction, {"LONG", "NEUTRAL"})
        self.assertGreaterEqual(signal.confidence, 0)
        self.assertTrue(signal.indicators)

    def test_insufficient_history_is_neutral(self) -> None:
        signal = SignalEngine().analyze("BTC_USDT_PERP", "15m", candles("up")[:5])

        self.assertEqual(signal.direction, "NEUTRAL")
        self.assertEqual(signal.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
