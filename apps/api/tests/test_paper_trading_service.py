from __future__ import annotations

import unittest

from app import models
from app.services.paper_trading_service import PaperTradingService


class PaperTradingServiceMathTest(unittest.TestCase):
    def test_long_pnl_uses_leveraged_quantity(self) -> None:
        service = PaperTradingService.__new__(PaperTradingService)
        position = models.PaperPosition(
            symbol="BTC_USDT_PERP",
            side="LONG",
            entry_price=100.0,
            current_price=110.0,
            size=10.0,
            leverage=2.0,
            margin_used=10.0,
        )

        self.assertAlmostEqual(service._pnl(position, 110.0), 2.0)

    def test_short_pnl_uses_inverse_price_move(self) -> None:
        service = PaperTradingService.__new__(PaperTradingService)
        position = models.PaperPosition(
            symbol="BTC_USDT_PERP",
            side="SHORT",
            entry_price=100.0,
            current_price=90.0,
            size=10.0,
            leverage=2.0,
            margin_used=10.0,
        )

        self.assertAlmostEqual(service._pnl(position, 90.0), 2.0)


if __name__ == "__main__":
    unittest.main()
