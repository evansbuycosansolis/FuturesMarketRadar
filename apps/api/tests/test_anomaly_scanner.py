from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app import models
from app.services.anomaly_scanner import scan_futures_anomalies


def snapshot(
    symbol: str,
    timestamp: datetime,
    price: float,
    quote_volume: float,
    *,
    high_24h: float = 1.25,
    low_24h: float = 0.75,
) -> models.MarketSnapshot:
    return models.MarketSnapshot(
        symbol=symbol,
        price=price,
        price_change_24h=(price - 1.0) * 100,
        volume_24h=quote_volume,
        quote_volume_24h=quote_volume,
        high_24h=high_24h,
        low_24h=low_24h,
        open_interest=0.0,
        timestamp=timestamp,
    )


class FuturesAnomalyScannerTest(unittest.TestCase):
    def test_breakout_anomaly_requires_relative_move_and_volume(self) -> None:
        base = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
        history = []
        quote_volume = 100_000.0
        price = 1.0
        for index in range(30):
            quote_volume += 1_000
            price += 0.0003
            history.append(snapshot("WAKE_USDT_PERP", base + timedelta(minutes=index * 5), price, quote_volume))

        history.append(snapshot("WAKE_USDT_PERP", base + timedelta(minutes=150), 1.035, quote_volume + 20_000))

        breakouts, breakdowns = scan_futures_anomalies({"WAKE_USDT_PERP": history}, limit=5, min_quote_volume=50_000)

        self.assertFalse(breakdowns)
        self.assertEqual(len(breakouts), 1)
        candidate = breakouts[0]
        self.assertEqual(candidate.symbol, "WAKE_USDT_PERP")
        self.assertEqual(candidate.direction, "breakout")
        self.assertGreater(candidate.z_move_5m, 3.0)
        self.assertGreater(candidate.volume_ratio_1m, 5.0)
        self.assertIn("VOL_SPIKE_5X", candidate.reason_tags)


if __name__ == "__main__":
    unittest.main()
