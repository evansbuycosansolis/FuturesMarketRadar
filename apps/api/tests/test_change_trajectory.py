from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app import models
from app.routes.market import _build_change_momentum_item, _session_cells_for_history


def snapshot(symbol: str, timestamp: datetime, change: float, price: float = 1.0) -> models.MarketSnapshot:
    return models.MarketSnapshot(
        symbol=symbol,
        price=price,
        price_change_24h=change,
        volume_24h=1000.0,
        quote_volume_24h=1000.0,
        high_24h=price * 1.05,
        low_24h=price * 0.95,
        open_interest=0.0,
        timestamp=timestamp,
    )


class ChangeTrajectoryTest(unittest.TestCase):
    def test_recovery_item_uses_trough_as_window_anchor(self) -> None:
        base = datetime(2026, 6, 18, 23, 0, tzinfo=timezone.utc)
        history = [
            snapshot("TEST_USDT_PERP", base, 4.0, price=1.0),
            snapshot("TEST_USDT_PERP", base + timedelta(minutes=5), -8.0, price=0.9),
            snapshot("TEST_USDT_PERP", base + timedelta(minutes=10), -2.0, price=0.95),
            snapshot("TEST_USDT_PERP", base + timedelta(minutes=15), 3.0, price=1.08),
        ]

        item = _build_change_momentum_item("TEST_USDT_PERP", history, anchor="trough", expected_samples=4)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.previous_change_24h, -8.0)
        self.assertEqual(item.previous_timestamp, history[1].timestamp)
        self.assertEqual(item.delta_5m, 5.0)
        self.assertEqual(item.delta_window, 11.0)
        self.assertEqual(item.anchor_price, 0.9)
        self.assertEqual(item.price_delta_window_pct, 20.0)
        self.assertEqual(item.sample_coverage_pct, 100.0)
        self.assertEqual(item.max_gap_minutes, 5.0)
        self.assertEqual(item.data_quality, "strong")
        self.assertEqual(item.direction, "increasing")
        self.assertEqual(item.strength, "strong")

    def test_fading_item_uses_peak_as_window_anchor(self) -> None:
        base = datetime(2026, 6, 19, 7, 0, tzinfo=timezone.utc)
        history = [
            snapshot("FADE_USDT_PERP", base, 42.0),
            snapshot("FADE_USDT_PERP", base + timedelta(minutes=5), 58.0),
            snapshot("FADE_USDT_PERP", base + timedelta(minutes=10), 51.0),
        ]

        item = _build_change_momentum_item("FADE_USDT_PERP", history, anchor="peak")

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.previous_change_24h, 58.0)
        self.assertEqual(item.previous_timestamp, history[1].timestamp)
        self.assertEqual(item.delta_5m, -7.0)
        self.assertEqual(item.delta_window, -7.0)
        self.assertEqual(item.data_quality, "thin")
        self.assertEqual(item.direction, "decreasing")
        self.assertEqual(item.strength, "moderate")

    def test_sparse_snapshot_history_is_marked_partial_or_thin(self) -> None:
        base = datetime(2026, 6, 19, 7, 0, tzinfo=timezone.utc)
        history = [
            snapshot("GAPPY_USDT_PERP", base, 0.0, price=1.0),
            snapshot("GAPPY_USDT_PERP", base + timedelta(minutes=5), 2.0, price=1.01),
            snapshot("GAPPY_USDT_PERP", base + timedelta(minutes=45), 4.0, price=1.02),
        ]

        item = _build_change_momentum_item("GAPPY_USDT_PERP", history, anchor="earliest", expected_samples=10)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.sample_coverage_pct, 30.0)
        self.assertEqual(item.max_gap_minutes, 40.0)
        self.assertEqual(item.data_quality, "thin")

    def test_session_cells_report_5m_delta_samples_and_pressure(self) -> None:
        base = datetime(2026, 6, 18, 23, 0, tzinfo=timezone.utc)
        history = [
            snapshot("FLOW_USDT_PERP", base, 0.0),
            snapshot("FLOW_USDT_PERP", base + timedelta(minutes=5), 1.0),
            snapshot("FLOW_USDT_PERP", base + timedelta(minutes=10), 3.5),
            snapshot("FLOW_USDT_PERP", base + timedelta(hours=8, minutes=5), 2.0),
        ]

        dominant, summary, cells = _session_cells_for_history(history)
        asian = next(cell for cell in cells if cell.session == "Asian")
        london = next(cell for cell in cells if cell.session == "London")

        self.assertEqual(asian.samples, 2)
        self.assertEqual(asian.net_delta, 3.5)
        self.assertEqual(asian.average_5m_delta, 1.75)
        self.assertEqual(asian.direction, "up")
        self.assertEqual(london.samples, 1)
        self.assertEqual(london.net_delta, -1.5)
        self.assertEqual(london.direction, "down")
        self.assertEqual(dominant, "Asian")
        self.assertIn("Asian shows strongest buying pressure", summary)


if __name__ == "__main__":
    unittest.main()
