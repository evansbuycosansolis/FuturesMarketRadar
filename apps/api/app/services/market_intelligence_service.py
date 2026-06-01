from __future__ import annotations

import asyncio
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from math import tanh
from urllib.parse import urlparse

import httpx
from sqlalchemy import desc, select

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import (
    AssetSentimentRead,
    MarketIntelligenceRunRead,
    MarketIntelligenceSummaryResponse,
)


@dataclass(frozen=True)
class NewsSource:
    name: str
    url: str
    weight: float = 1.0


@dataclass
class FeedItem:
    source: NewsSource
    title: str
    url: str
    summary: str
    published_at: datetime | None


@dataclass
class ScoredMention:
    item: FeedItem
    asset: str
    score: float
    confidence: float
    themes: list[str]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = " ".join(data.split())
            if len(text) >= 24:
                self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


ASSETS = {
    "BTC": {
        "symbol": "BTC_USDT_PERP",
        "terms": ["bitcoin", "btc", "btcusd", "btcusdt"],
    },
    "ETH": {
        "symbol": "ETH_USDT_PERP",
        "terms": ["ethereum", "ether", "eth", "ethusd", "ethusdt"],
    },
    "XRP": {
        "symbol": "XRP_USDT_PERP",
        "terms": ["xrp", "ripple"],
    },
    "SOL": {
        "symbol": "SOL_USDT_PERP",
        "terms": ["solana", "sol", "solusd", "solusdt"],
    },
}

DEFAULT_SOURCES = [
    NewsSource("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", 1.18),
    NewsSource("Cointelegraph", "https://cointelegraph.com/rss", 1.05),
    NewsSource("Decrypt", "https://decrypt.co/feed", 1.0),
    NewsSource("CryptoSlate", "https://cryptoslate.com/feed/", 0.95),
    NewsSource("The Block", "https://www.theblock.co/rss.xml", 1.12),
    NewsSource("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/", 0.9),
    NewsSource("NewsBTC", "https://www.newsbtc.com/feed/", 0.82),
    NewsSource("Bitcoinist", "https://bitcoinist.com/feed/", 0.8),
    NewsSource("AMBCrypto", "https://ambcrypto.com/feed/", 0.78),
    NewsSource("BeInCrypto", "https://beincrypto.com/feed/", 0.86),
    NewsSource("U.Today", "https://u.today/rss", 0.82),
    NewsSource("CryptoPotato", "https://cryptopotato.com/feed/", 0.82),
    NewsSource("FXStreet Crypto", "https://www.fxstreet.com/rss/cryptocurrencies", 0.96),
    NewsSource("CNBC Crypto", "https://www.cnbc.com/id/10000664/device/rss/rss.html", 1.05),
    NewsSource("Investing.com Crypto", "https://www.investing.com/rss/news_301.rss", 0.94),
    NewsSource("Daily Hodl", "https://dailyhodl.com/feed/", 0.75),
    NewsSource("Crypto Briefing", "https://cryptobriefing.com/feed/", 0.86),
    NewsSource("Blockworks", "https://blockworks.co/feed", 1.02),
    NewsSource("Bankless", "https://www.bankless.com/rss.xml", 0.84),
    NewsSource("99Bitcoins", "https://99bitcoins.com/feed/", 0.68),
    NewsSource("CoinJournal", "https://coinjournal.net/news/feed/", 0.74),
    NewsSource("CoinGape", "https://coingape.com/feed/", 0.72),
    NewsSource("CryptoNews", "https://cryptonews.com/news/feed/", 0.82),
    NewsSource("Bitcoin.com News", "https://news.bitcoin.com/feed/", 0.86),
    NewsSource("Finbold Crypto", "https://finbold.com/category/cryptocurrency-news/feed/", 0.78),
    NewsSource("Forbes Crypto", "https://www.forbes.com/crypto-blockchain/feed/", 1.02),
    NewsSource("Nasdaq Crypto", "https://www.nasdaq.com/feed/rssoutbound?category=Cryptocurrency", 0.96),
    NewsSource("MarketWatch Crypto", "https://feeds.content.dowjones.io/public/rss/mw_crypto", 0.98),
    NewsSource("Watcher Guru", "https://watcher.guru/news/feed", 0.7),
    NewsSource("CoinPedia", "https://coinpedia.org/feed/", 0.7),
    NewsSource("NullTX", "https://nulltx.com/feed/", 0.62),
    NewsSource("CryptoGlobe", "https://www.cryptoglobe.com/latest/feed/", 0.76),
]

POSITIVE_TERMS = {
    "accumulation": 1.0,
    "adoption": 1.1,
    "approval": 1.2,
    "approved": 1.2,
    "breakout": 1.4,
    "bullish": 1.5,
    "buy": 0.7,
    "climbs": 0.8,
    "demand": 0.8,
    "etf inflow": 1.35,
    "gain": 0.8,
    "gains": 0.8,
    "growth": 0.8,
    "institutional": 0.75,
    "inflow": 1.0,
    "outperform": 1.0,
    "partnership": 0.9,
    "rally": 1.4,
    "recover": 0.8,
    "recovery": 0.8,
    "record high": 1.5,
    "resistance break": 1.3,
    "surge": 1.3,
    "upgrade": 0.9,
    "whale accumulation": 1.2,
}

NEGATIVE_TERMS = {
    "bearish": 1.5,
    "crackdown": 1.3,
    "decline": 0.9,
    "delist": 1.2,
    "dump": 1.3,
    "etf outflow": 1.35,
    "exploit": 1.4,
    "fall": 0.9,
    "falls": 0.9,
    "fraud": 1.4,
    "hack": 1.5,
    "lawsuit": 1.2,
    "liquidation": 1.3,
    "outflow": 1.0,
    "plunge": 1.5,
    "reject": 1.2,
    "rejected": 1.2,
    "risk-off": 1.1,
    "scam": 1.4,
    "sell-off": 1.4,
    "slump": 1.2,
    "sec sues": 1.3,
    "support break": 1.3,
    "whale sells": 1.2,
}

THEME_TERMS = {
    "ETF flows": ["etf", "inflow", "outflow"],
    "Regulation": ["sec", "cftc", "regulation", "lawsuit", "court", "compliance"],
    "Institutional demand": ["institutional", "fund", "treasury", "blackrock", "fidelity"],
    "Network / upgrade": ["upgrade", "mainnet", "validator", "staking", "throughput"],
    "Security risk": ["hack", "exploit", "breach", "scam"],
    "Market structure": ["liquidation", "open interest", "funding", "whale", "resistance", "support"],
}


class MarketIntelligenceService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def run_scan(self, reason: str = "scheduled") -> models.MarketIntelligenceRun:
        if self._running:
            with SessionLocal() as db:
                existing = db.scalar(select(models.MarketIntelligenceRun).order_by(desc(models.MarketIntelligenceRun.created_at)))
                if existing is not None:
                    return existing

        self._running = True
        run = models.MarketIntelligenceRun(reason=reason, status="running")
        with SessionLocal() as db:
            db.add(run)
            db.commit()
            db.refresh(run)

        try:
            sources = DEFAULT_SOURCES[: max(1, self._settings.market_intelligence_source_limit)]
            items = await self._collect_items(sources)
            scored = await self._score_items(items)
            self._store_results(run.id, sources_checked=len(sources), articles_scanned=len(items), scored=scored)
        except Exception as exc:
            with SessionLocal() as db:
                failed_run = db.get(models.MarketIntelligenceRun, run.id)
                if failed_run is not None:
                    failed_run.status = "failed"
                    failed_run.error = str(exc)
                    failed_run.completed_at = models.utc_now()
                    db.add(
                        models.CopilotLog(
                            category="market_intel",
                            severity="warning",
                            message="Market intelligence scan failed.",
                            payload_json={"error": str(exc)},
                        )
                    )
                    db.commit()
            raise
        finally:
            self._running = False

        with SessionLocal() as db:
            refreshed = db.get(models.MarketIntelligenceRun, run.id)
            if refreshed is None:
                raise RuntimeError("Market intelligence run disappeared after scan.")
            return refreshed

    def summary(self) -> MarketIntelligenceSummaryResponse:
        with SessionLocal() as db:
            latest_run = db.scalar(select(models.MarketIntelligenceRun).order_by(desc(models.MarketIntelligenceRun.created_at)))
            snapshots: list[models.AssetSentimentSnapshot] = []
            if latest_run is not None:
                snapshots = list(
                    db.scalars(
                        select(models.AssetSentimentSnapshot)
                        .where(models.AssetSentimentSnapshot.run_id == latest_run.id)
                        .order_by(models.AssetSentimentSnapshot.asset)
                    )
                )

        return MarketIntelligenceSummaryResponse(
            enabled=self._settings.enable_market_intelligence,
            interval_minutes=self._settings.market_intelligence_interval_minutes,
            latest_run=self._run_schema(latest_run) if latest_run is not None else None,
            assets=[self._snapshot_schema(snapshot) for snapshot in snapshots],
            note="Decision support only. These sentiment scores never place or approve trades.",
        )

    async def _collect_items(self, sources: list[NewsSource]) -> list[FeedItem]:
        timeout = httpx.Timeout(self._settings.market_intelligence_article_timeout_seconds)
        limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, limits=limits) as client:
            results = await asyncio.gather(*(self._fetch_feed(client, source) for source in sources), return_exceptions=True)

        seen: set[str] = set()
        items: list[FeedItem] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            for item in result:
                key = hashlib.sha256((item.url or item.title).encode("utf-8", errors="ignore")).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
        return items

    async def _fetch_feed(self, client: httpx.AsyncClient, source: NewsSource) -> list[FeedItem]:
        response = await client.get(source.url, headers={"User-Agent": "EvansFuturesTradingCopilot/1.0"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        raw_items = root.findall(".//item")
        if not raw_items:
            raw_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        items: list[FeedItem] = []
        for element in raw_items[: self._settings.market_intelligence_articles_per_source]:
            title = self._node_text(element, "title")
            link = self._node_text(element, "link")
            if not link:
                atom_link = element.find("{http://www.w3.org/2005/Atom}link")
                link = atom_link.attrib.get("href", "") if atom_link is not None else ""
            summary = self._node_text(element, "description") or self._node_text(element, "summary")
            published = self._parse_date(self._node_text(element, "pubDate") or self._node_text(element, "published") or self._node_text(element, "updated"))
            if title and link:
                items.append(
                    FeedItem(
                        source=source,
                        title=html.unescape(self._strip_tags(title)),
                        url=link,
                        summary=html.unescape(self._strip_tags(summary)),
                        published_at=published,
                    )
                )
        return items

    async def _score_items(self, items: list[FeedItem]) -> list[ScoredMention]:
        if not self._settings.market_intelligence_fetch_article_bodies:
            return [mention for item in items for mention in self._score_item(item, "")]

        timeout = httpx.Timeout(self._settings.market_intelligence_article_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            tasks = [self._fetch_article_text(client, item) for item in items]
            bodies = await asyncio.gather(*tasks, return_exceptions=True)

        mentions: list[ScoredMention] = []
        for item, body in zip(items, bodies, strict=False):
            article_text = "" if isinstance(body, Exception) else str(body)
            mentions.extend(self._score_item(item, article_text))
        return mentions

    async def _fetch_article_text(self, client: httpx.AsyncClient, item: FeedItem) -> str:
        response = await client.get(item.url, headers={"User-Agent": "EvansFuturesTradingCopilot/1.0"})
        response.raise_for_status()
        parser = TextExtractor()
        parser.feed(response.text[:250_000])
        return parser.text()[:12_000]

    def _score_item(self, item: FeedItem, article_text: str) -> list[ScoredMention]:
        title_text = item.title.lower()
        focus_text = f"{item.title}. {item.summary}".lower()
        text = f"{focus_text}. {article_text}".lower()
        if not text.strip():
            return []

        base_score, strength = self._score_text(text)
        themes = self._themes(text)
        mentions: list[ScoredMention] = []
        for asset, config in ASSETS.items():
            relevance = self._asset_relevance(title_text, config["terms"])
            if relevance <= 0:
                continue
            weighted_score = max(-1.0, min(1.0, base_score * item.source.weight))
            confidence = min(1.0, 0.25 + relevance * 0.2 + strength * 0.18)
            mentions.append(
                ScoredMention(
                    item=item,
                    asset=asset,
                    score=round(weighted_score, 4),
                    confidence=round(confidence, 4),
                    themes=themes,
                )
            )
        return mentions

    def _store_results(self, run_id: int, sources_checked: int, articles_scanned: int, scored: list[ScoredMention]) -> None:
        grouped: dict[str, list[ScoredMention]] = defaultdict(list)
        for mention in scored:
            grouped[mention.asset].append(mention)

        with SessionLocal() as db:
            run = db.get(models.MarketIntelligenceRun, run_id)
            if run is None:
                raise RuntimeError("Market intelligence run was not found.")

            for asset, config in ASSETS.items():
                mentions = grouped.get(asset, [])
                weighted_total = sum(mention.score * mention.confidence for mention in mentions)
                confidence_total = sum(mention.confidence for mention in mentions)
                score = weighted_total / confidence_total if confidence_total else 0.0
                positive_count = sum(1 for mention in mentions if mention.score >= 0.2)
                negative_count = sum(1 for mention in mentions if mention.score <= -0.2)
                neutral_count = max(0, len(mentions) - positive_count - negative_count)
                source_counts = Counter(mention.item.source.name for mention in mentions)
                theme_counts = Counter(theme for mention in mentions for theme in mention.themes)
                example_links = [
                    {
                        "title": mention.item.title[:180],
                        "source": mention.item.source.name,
                        "url": mention.item.url,
                    }
                    for mention in sorted(mentions, key=lambda item: item.confidence, reverse=True)[:4]
                ]
                previous_scores = list(
                    db.scalars(
                        select(models.AssetSentimentSnapshot.sentiment_score)
                        .where(models.AssetSentimentSnapshot.asset == asset)
                        .order_by(desc(models.AssetSentimentSnapshot.created_at))
                        .limit(55)
                    )
                )
                series = [score, *previous_scores]
                snapshot = models.AssetSentimentSnapshot(
                    run_id=run_id,
                    asset=asset,
                    symbol=str(config["symbol"]),
                    sentiment_score=round(score, 4),
                    confidence=round(confidence_total / len(mentions), 4) if mentions else 0.0,
                    article_count=len(mentions),
                    positive_count=positive_count,
                    negative_count=negative_count,
                    neutral_count=neutral_count,
                    ma_3_score=round(sum(series[:3]) / len(series[:3]), 4) if series[:3] else 0.0,
                    ma_8_score=round(sum(series[:8]) / len(series[:8]), 4) if series[:8] else 0.0,
                    ma_56_score=round(sum(series[:56]) / len(series[:56]), 4) if series[:56] else 0.0,
                    themes_json=[theme for theme, _count in theme_counts.most_common(5)],
                    source_counts_json=dict(source_counts.most_common(8)),
                    example_links_json=example_links,
                )
                db.add(snapshot)

            run.status = "completed"
            run.sources_checked = sources_checked
            run.articles_scanned = articles_scanned
            run.matched_articles = len(scored)
            run.completed_at = models.utc_now()
            db.add(
                models.CopilotLog(
                    category="market_intel",
                    severity="info",
                    message="Market intelligence sentiment scan completed.",
                    payload_json={
                        "sources_checked": sources_checked,
                        "articles_scanned": articles_scanned,
                        "matched_articles": len(scored),
                    },
                )
            )
            db.commit()

    def _score_text(self, text: str) -> tuple[float, float]:
        positive = sum(weight * self._count_term(text, term) for term, weight in POSITIVE_TERMS.items())
        negative = sum(weight * self._count_term(text, term) for term, weight in NEGATIVE_TERMS.items())
        total = positive + negative
        if total <= 0:
            return 0.0, 0.0
        raw = (positive - negative) / max(total, 1.0)
        return tanh(raw * 1.35), min(1.0, total / 10.0)

    def _asset_relevance(self, text: str, terms: list[str]) -> int:
        return sum(self._count_term(text, term) for term in terms)

    def _themes(self, text: str) -> list[str]:
        themes = []
        for theme, terms in THEME_TERMS.items():
            if any(self._count_term(text, term) > 0 for term in terms):
                themes.append(theme)
        return themes or ["General market tone"]

    def _count_term(self, text: str, term: str) -> int:
        if " " in term or "-" in term:
            return text.count(term)
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))

    def _snapshot_schema(self, snapshot: models.AssetSentimentSnapshot) -> AssetSentimentRead:
        return AssetSentimentRead(
            asset=snapshot.asset,
            symbol=snapshot.symbol,
            sentiment_score=snapshot.sentiment_score,
            confidence=snapshot.confidence,
            article_count=snapshot.article_count,
            positive_count=snapshot.positive_count,
            negative_count=snapshot.negative_count,
            neutral_count=snapshot.neutral_count,
            ma_3_score=snapshot.ma_3_score,
            ma_8_score=snapshot.ma_8_score,
            ma_56_score=snapshot.ma_56_score,
            label=self._label(snapshot.sentiment_score),
            themes=list(snapshot.themes_json or []),
            source_counts={str(key): int(value) for key, value in (snapshot.source_counts_json or {}).items()},
            example_links=list(snapshot.example_links_json or []),
            created_at=snapshot.created_at,
        )

    def _run_schema(self, run: models.MarketIntelligenceRun) -> MarketIntelligenceRunRead:
        return MarketIntelligenceRunRead.model_validate(run, from_attributes=True)

    def _label(self, score: float) -> str:
        if score >= 0.55:
            return "Strong bullish"
        if score >= 0.2:
            return "Bullish"
        if score <= -0.55:
            return "Strong bearish"
        if score <= -0.2:
            return "Bearish"
        return "Neutral"

    def _node_text(self, element: ET.Element, name: str) -> str:
        node = element.find(name)
        if node is None:
            node = element.find(f"{{http://www.w3.org/2005/Atom}}{name}")
        return "".join(node.itertext()).strip() if node is not None else ""

    def _strip_tags(self, text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text or "").strip()

    def _parse_date(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None


def source_host(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")
