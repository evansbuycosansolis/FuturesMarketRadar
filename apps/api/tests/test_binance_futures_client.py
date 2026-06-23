from __future__ import annotations

import unittest

from app.services.binance_futures_client import pionex_perp_to_binance_symbol


class BinanceFuturesClientTest(unittest.TestCase):
    def test_maps_pionex_perp_symbol_to_binance_usdm_symbol(self) -> None:
        self.assertEqual(pionex_perp_to_binance_symbol("BTC_USDT_PERP"), "BTCUSDT")
        self.assertEqual(pionex_perp_to_binance_symbol("eth_usdt_perp"), "ETHUSDT")


if __name__ == "__main__":
    unittest.main()
