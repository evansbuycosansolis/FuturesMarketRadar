from __future__ import annotations

import unittest

from app.config import Settings
from app.services.market_intelligence_service import FeedItem, MarketIntelligenceService, NewsSource


class MarketIntelligenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MarketIntelligenceService(Settings())
        self.source = NewsSource("Test Source", "https://example.com/feed", 1.0)

    def test_scores_bullish_bitcoin_article(self) -> None:
        item = FeedItem(
            source=self.source,
            title="Bitcoin ETF inflow sparks bullish breakout",
            url="https://example.com/btc",
            summary="Institutional demand and whale accumulation helped BTC rally.",
            published_at=None,
        )

        mentions = self.service._score_item(item, "")

        btc = next(mention for mention in mentions if mention.asset == "BTC")
        self.assertGreater(btc.score, 0.2)
        self.assertIn("ETF flows", btc.themes)

    def test_scores_bearish_xrp_article(self) -> None:
        item = FeedItem(
            source=self.source,
            title="XRP falls as lawsuit risk returns",
            url="https://example.com/xrp",
            summary="The market turned bearish after renewed SEC lawsuit headlines.",
            published_at=None,
        )

        mentions = self.service._score_item(item, "")

        xrp = next(mention for mention in mentions if mention.asset == "XRP")
        self.assertLess(xrp.score, -0.2)
        self.assertIn("Regulation", xrp.themes)

    def test_ignores_unrelated_article(self) -> None:
        item = FeedItem(
            source=self.source,
            title="Stock futures rise before payrolls",
            url="https://example.com/stocks",
            summary="Equity investors await macro data.",
            published_at=None,
        )

        mentions = self.service._score_item(item, "")

        self.assertEqual(mentions, [])


if __name__ == "__main__":
    unittest.main()
