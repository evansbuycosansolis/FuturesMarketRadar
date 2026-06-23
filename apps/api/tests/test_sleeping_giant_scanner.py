from __future__ import annotations

import unittest

from app.routes.market import _price_relevance_multiplier
from app.services.pionex_client import PionexKline
from app.services.sleeping_giant_scanner import RecentAwakeningScanner, SleepingGiantConfig, SleepingGiantScanner


def compressed_candles(count: int = 90, *, price: float = 100.0, volume: float = 100.0) -> list[PionexKline]:
    candles: list[PionexKline] = []
    for index in range(count):
        wiggle = 0.05 if index % 2 == 0 else -0.05
        open_price = price + wiggle
        close = price - wiggle
        candles.append(
            PionexKline(
                time=index,
                open=open_price,
                close=close,
                high=price + 0.2,
                low=price - 0.2,
                volume=volume,
            )
        )
    return candles


def noisy_then_compressed() -> list[PionexKline]:
    candles: list[PionexKline] = []
    price = 100.0
    for index in range(35):
        open_price = price
        close = price + (0.8 if index % 2 == 0 else -0.75)
        candles.append(
            PionexKline(
                time=index,
                open=open_price,
                close=close,
                high=max(open_price, close) + 0.35,
                low=min(open_price, close) - 0.35,
                volume=160.0,
            )
        )
        price = close
    quiet = compressed_candles(time_count := 90, price=100.0, volume=100.0)
    return candles + [
        PionexKline(
            time=index + len(candles),
            open=candle.open,
            close=candle.close,
            high=candle.high,
            low=candle.low,
            volume=candle.volume,
        )
        for index, candle in enumerate(quiet[:time_count])
    ]


class SleepingGiantScannerTest(unittest.TestCase):
    def test_bullish_awakening_from_latest_abnormal_candle(self) -> None:
        candles = compressed_candles(200)
        candles.append(PionexKline(time=199, open=100.0, close=100.85, high=100.9, low=99.95, volume=180.0))
        candles.append(PionexKline(time=200, open=100.1, close=101.45, high=101.55, low=99.95, volume=220.0))

        setup = SleepingGiantScanner().analyze_symbol("TEST_USDT_PERP", candles)

        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.direction, "bullish")
        self.assertAlmostEqual(setup.average_candle_size, 0.4, places=6)
        self.assertAlmostEqual(setup.latest_candle_size, 1.6, places=6)
        self.assertEqual(setup.awakening_phase, "giant_awakening")
        self.assertGreaterEqual(setup.height_ratio, 2.0)
        self.assertGreaterEqual(setup.volume_ratio, 2.0)
        self.assertGreater(setup.body_strength, 0.6)
        self.assertGreaterEqual(setup.range_burst_score, 2.0)
        self.assertGreaterEqual(setup.volume_burst_score, 2.0)
        self.assertGreaterEqual(setup.range_expansion_ratio, 2.0)
        self.assertGreaterEqual(setup.volume_expansion_ratio, 2.0)

    def test_bearish_awakening_from_latest_abnormal_candle(self) -> None:
        candles = compressed_candles(200)
        candles.append(PionexKline(time=199, open=100.0, close=99.15, high=100.05, low=99.1, volume=180.0))
        candles.append(PionexKline(time=200, open=99.9, close=99.25, high=100.05, low=99.2, volume=220.0))

        setup = SleepingGiantScanner().analyze_symbol("TEST_USDT_PERP", candles)

        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.direction, "bearish")

    def test_classifies_large_indecision_candle_as_liquidity_spike(self) -> None:
        candles = compressed_candles(200)
        candles.append(PionexKline(time=199, open=100.0, close=100.85, high=100.9, low=99.95, volume=180.0))
        candles.append(PionexKline(time=200, open=100.0, close=100.02, high=100.9, low=99.1, volume=300.0))

        setup = SleepingGiantScanner().analyze_symbol("TEST_USDT_PERP", candles)

        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.awakening_phase, "liquidity_spike")
        self.assertLess(setup.body_strength, 0.3)

    def test_rejects_large_but_statistically_normal_candle(self) -> None:
        candles: list[PionexKline] = []
        for index in range(201):
            size = 0.4 if index % 2 == 0 else 1.4
            candles.append(
                PionexKline(
                    time=index,
                    open=100.0,
                    close=100.1,
                    high=100.0 + size / 2,
                    low=100.0 - size / 2,
                    volume=100.0 + (index % 5) * 40,
                )
            )
        candles.append(PionexKline(time=200, open=100.0, close=100.9, high=101.0, low=99.9, volume=190.0))

        setup = SleepingGiantScanner().analyze_symbol("NOISY_USDT_PERP", candles)

        self.assertIsNone(setup)

    def test_rejects_sigma_only_move_below_median_watch_threshold(self) -> None:
        candles: list[PionexKline] = []
        for index in range(201):
            size = 1.0 if index < 51 else 0.2
            candles.append(
                PionexKline(
                    time=index,
                    open=100.0,
                    close=100.0,
                    high=100.0 + size / 2,
                    low=100.0 - size / 2,
                    volume=100.0,
                )
            )
        candles.append(PionexKline(time=200, open=100.0, close=100.7, high=100.75, low=99.95, volume=300.0))

        setup = SleepingGiantScanner().analyze_symbol("SIGMA_ONLY_USDT_PERP", candles)

        self.assertIsNone(setup)

    def test_rejects_single_late_abnormal_candle_when_previous_is_not_abnormal(self) -> None:
        candles = compressed_candles(200)
        candles.append(PionexKline(time=199, open=100.0, close=100.55, high=100.6, low=99.95, volume=180.0))
        candles.append(PionexKline(time=200, open=100.55, close=101.55, high=101.6, low=100.5, volume=300.0))

        setup = SleepingGiantScanner().analyze_symbol("BTR_STYLE_USDT_PERP", candles)

        self.assertIsNone(setup)

    def test_recent_mode_surfaces_single_candle_awakenings(self) -> None:
        candles = compressed_candles(362)
        candles.append(PionexKline(time=362, open=100.0, close=100.45, high=100.5, low=99.95, volume=180.0))
        candles.append(PionexKline(time=363, open=100.45, close=101.55, high=101.65, low=100.4, volume=300.0))

        strict_setup = SleepingGiantScanner(
            SleepingGiantConfig(baseline_candles=362, require_sleep_window=True, require_two_candle_confirmation=True)
        ).analyze_symbol("RECENT_USDT_PERP", candles)
        recent_setup = SleepingGiantScanner(
            SleepingGiantConfig(baseline_candles=362, require_sleep_window=False, require_two_candle_confirmation=False)
        ).analyze_symbol("RECENT_USDT_PERP", candles)

        self.assertIsNone(strict_setup)
        self.assertIsNotNone(recent_setup)
        assert recent_setup is not None
        self.assertEqual(recent_setup.direction, "bullish")
        self.assertGreaterEqual(recent_setup.height_ratio, 2.0)

    def test_legacy_recent_scanner_detects_recent_box_breakout(self) -> None:
        candles = compressed_candles(362)
        candles.append(PionexKline(time=362, open=100.1, close=101.35, high=101.45, low=100.0, volume=240.0))

        setup = RecentAwakeningScanner(
            SleepingGiantConfig(
                timeframe="1H",
                baseline_candles=362,
                compression_min_candles=30,
                compression_max_candles=80,
                require_sleep_window=False,
                require_two_candle_confirmation=False,
            )
        ).analyze_symbol("RECENT_BOX_USDT_PERP", candles)

        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.direction, "bullish")
        self.assertGreaterEqual(setup.range_expansion_ratio, 1.5)
        self.assertGreaterEqual(setup.volume_expansion_ratio, 1.2)

    def test_legacy_recent_scanner_rejects_expansion_without_box_breakout(self) -> None:
        candles = compressed_candles(362)
        candles.append(PionexKline(time=362, open=100.05, close=100.1, high=100.45, low=99.6, volume=240.0))

        setup = RecentAwakeningScanner(
            SleepingGiantConfig(
                timeframe="1H",
                baseline_candles=362,
                compression_min_candles=30,
                compression_max_candles=80,
                require_sleep_window=False,
                require_two_candle_confirmation=False,
            )
        ).analyze_symbol("NO_BREAKOUT_USDT_PERP", candles)

        self.assertIsNone(setup)

    def test_rejects_market_that_already_awoke_inside_recent_sleep_window(self) -> None:
        candles = compressed_candles(170)
        candles.append(PionexKline(time=170, open=100.0, close=101.25, high=101.3, low=99.95, volume=260.0))
        candles.extend(compressed_candles(29, price=101.0, volume=120.0))
        candles.append(PionexKline(time=199, open=101.0, close=102.0, high=102.05, low=100.95, volume=220.0))
        candles.append(PionexKline(time=200, open=102.0, close=103.05, high=103.1, low=101.95, volume=250.0))

        setup = SleepingGiantScanner().analyze_symbol("ALREADY_AWAKE_USDT_PERP", candles)

        self.assertIsNone(setup)

    def test_accepts_two_candle_expansion_sequence(self) -> None:
        candles = compressed_candles(200)
        candles.append(PionexKline(time=199, open=100.0, close=100.85, high=100.9, low=99.95, volume=180.0))
        candles.append(PionexKline(time=200, open=100.85, close=101.7, high=101.75, low=100.8, volume=190.0))

        setup = SleepingGiantScanner().analyze_symbol("TEST_USDT_PERP", candles)

        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.direction, "bullish")
        self.assertGreater(setup.breakout_score, 60)
        self.assertGreaterEqual(setup.two_candle_pressure, 2.0)

    def test_no_breakout_returns_none(self) -> None:
        setup = SleepingGiantScanner().analyze_symbol("TEST_USDT_PERP", compressed_candles())

        self.assertIsNone(setup)

    def test_scan_returns_ranked_setups(self) -> None:
        bullish = compressed_candles(200)
        bullish.append(PionexKline(time=199, open=100.0, close=100.85, high=100.9, low=99.95, volume=180.0))
        bullish.append(PionexKline(time=200, open=100.1, close=100.75, high=100.8, low=99.95, volume=220.0))
        quiet = compressed_candles()

        setups = SleepingGiantScanner().scan({"BULL_USDT_PERP": bullish, "QUIET_USDT_PERP": quiet})

        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].symbol, "BULL_USDT_PERP")

    def test_price_relevance_multiplier_quietly_downranks_large_mismatch(self) -> None:
        self.assertEqual(_price_relevance_multiplier(100.0, 100.5), 1.0)
        self.assertEqual(_price_relevance_multiplier(100.0, 101.5), 0.9)
        self.assertEqual(_price_relevance_multiplier(100.0, 104.0), 0.75)
        self.assertEqual(_price_relevance_multiplier(100.0, 108.0), 0.55)


if __name__ == "__main__":
    unittest.main()
