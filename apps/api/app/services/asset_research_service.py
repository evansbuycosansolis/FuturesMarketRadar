from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import func, select

from .. import models
from ..db import SessionLocal
from ..schemas import (
    AssetResearchResponse,
    AssetResearchSessionRead,
    AssetResearchSourceRead,
    MarketSessionMomentumCellRead,
)


SESSIONS_UTC = [
    ("Asian", 23, 7),
    ("London", 7, 15),
    ("New York", 15, 23),
]

KNOWN_ALIASES = {
    "BITCOIN": "BTC",
    "BTC": "BTC",
    "ETHEREUM": "ETH",
    "ETHER": "ETH",
    "ETH": "ETH",
    "RIPPLE": "XRP",
    "XRP": "XRP",
    "SOLANA": "SOL",
    "SOL": "SOL",
    "DOGECOIN": "DOGE",
    "DOGE": "DOGE",
    "BINANCE COIN": "BNB",
    "BNB": "BNB",
}


@dataclass(frozen=True)
class ResearchDocument:
    title: str
    source: str
    url: str
    text: str


def _clean_text(value: str | None, *, limit: int = 1200) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    compact = re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
    return compact[:limit].strip()


def _normalized_token(query: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", query).strip().upper()
    if cleaned in KNOWN_ALIASES:
        return KNOWN_ALIASES[cleaned]
    first = cleaned.split()[0] if cleaned else ""
    return KNOWN_ALIASES.get(first, first)


def _session_name(timestamp: datetime) -> tuple[str, int, int]:
    normalized = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    hour = normalized.astimezone(timezone.utc).hour
    for name, start_hour, end_hour in SESSIONS_UTC:
        if start_hour <= end_hour and start_hour <= hour < end_hour:
            return name, start_hour, end_hour
        if start_hour > end_hour and (hour >= start_hour or hour < end_hour):
            return name, start_hour, end_hour
    return "New York", 15, 23


def _direction(delta: float, samples: int) -> str:
    if samples < 2:
        return "insufficient"
    if delta >= 0.15:
        return "up"
    if delta <= -0.15:
        return "down"
    return "flat"


def _extract_who(text: str) -> str:
    patterns = [
        r"(?:created|founded|developed|launched) by ([^.]{3,120})",
        r"(?:founder|co-founder)s? (?:is|are|include|included) ([^.]{3,120})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1), limit=220).rstrip(", ")
    return "No clearly verified creator or issuer was found in the fetched public summaries."


def _extract_when(text: str, fallback: str | None) -> str:
    if fallback:
        return fallback
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if match:
        return f"Public summaries mention {match.group(0)}."
    return "No clear launch or founding date was found in the fetched public summaries."


def _extract_themes(documents: list[ResearchDocument]) -> list[str]:
    keywords = [
        "ETF",
        "regulation",
        "lawsuit",
        "upgrade",
        "mainnet",
        "partnership",
        "funding",
        "hack",
        "staking",
        "AI",
        "DeFi",
        "stablecoin",
        "institutional",
    ]
    joined = " ".join(document.title for document in documents)
    found = [keyword for keyword in keywords if re.search(rf"\b{re.escape(keyword)}\b", joined, flags=re.IGNORECASE)]
    return found[:6] or ["No dominant catalyst theme stood out from the fetched headlines."]


def _session_summary(cells: list[MarketSessionMomentumCellRead]) -> tuple[str, str]:
    valid_cells = [cell for cell in cells if cell.samples >= 2]
    if not valid_cells:
        return "Waiting", "Not enough stored 5-minute snapshots yet for a session read."

    strongest = max(valid_cells, key=lambda cell: abs(cell.net_delta))
    strongest_bias = "buying pressure" if strongest.net_delta > 0 else "selling pressure" if strongest.net_delta < 0 else "balanced flow"
    readable = {
        "up": "buying pressure",
        "down": "selling pressure",
        "flat": "balanced/flat",
        "insufficient": "thin data",
    }
    parts = [f"{cell.session}: {readable[cell.direction]} ({cell.net_delta:+.2f} pts)" for cell in valid_cells]
    return strongest.session, f"{strongest.session} shows strongest {strongest_bias} ({strongest.net_delta:+.2f} pts). " + "; ".join(parts)


class AssetResearchService:
    async def research(self, query: str) -> AssetResearchResponse:
        normalized = _normalized_token(query)
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            documents, name, symbol, asset_type, genesis_date, platform = await self._fetch_documents(client, query, normalized)

        combined_text = " ".join(document.text for document in documents if document.text)
        what = self._build_what(documents, query)
        who = _extract_who(combined_text)
        when = _extract_when(combined_text, genesis_date)
        where = platform or self._infer_where(combined_text, asset_type)
        session_support = self._build_session_support(normalized, symbol, query)
        recent_themes = _extract_themes(documents)
        risk_notes = self._risk_notes(asset_type, documents)
        what_to_watch_next = self._what_to_watch_next(session_support)
        sources = [
            AssetResearchSourceRead(title=document.title, source=document.source, url=document.url)
            for document in documents[:8]
        ]
        confidence = min(0.92, 0.28 + (len(sources) * 0.08) + (0.14 if session_support.matched_symbol else 0.0))
        summary_text = self._summary_text(
            name=name or query,
            symbol=symbol,
            asset_type=asset_type,
            what=what,
            who=who,
            where=where,
            when=when,
            session=session_support,
            themes=recent_themes,
            risks=risk_notes,
            watch=what_to_watch_next,
            confidence=confidence,
        )

        return AssetResearchResponse(
            query=query,
            normalized_query=normalized,
            asset_type=asset_type,
            name=name or query,
            symbol=symbol,
            what=what,
            who=who,
            where=where,
            when=when,
            session_support=session_support,
            recent_themes=recent_themes,
            risk_notes=risk_notes,
            what_to_watch_next=what_to_watch_next,
            confidence=round(confidence, 2),
            summary_text=summary_text,
            sources=sources,
        )

    async def _fetch_documents(
        self,
        client: httpx.AsyncClient,
        query: str,
        normalized: str,
    ) -> tuple[list[ResearchDocument], str | None, str | None, str, str | None, str | None]:
        documents: list[ResearchDocument] = []
        name: str | None = None
        symbol: str | None = normalized if normalized else None
        asset_type = "unknown"
        genesis_date: str | None = None
        platform: str | None = None

        coingecko_docs, cg_name, cg_symbol, cg_genesis, cg_platform = await self._coingecko(client, query)
        if coingecko_docs:
            documents.extend(coingecko_docs)
            name = cg_name or name
            symbol = cg_symbol or symbol
            genesis_date = cg_genesis or genesis_date
            platform = cg_platform or platform
            asset_type = "crypto/token"

        wiki_doc = await self._wikipedia(client, query)
        if wiki_doc:
            documents.append(wiki_doc)
            name = name or wiki_doc.title

        ddg_doc = await self._duckduckgo(client, query)
        if ddg_doc:
            documents.append(ddg_doc)

        news_docs = await self._google_news(client, f"{query} {normalized} crypto stock token")
        documents.extend(news_docs)

        seen: set[str] = set()
        unique_documents: list[ResearchDocument] = []
        for document in documents:
            key = document.url or document.title
            if key not in seen and (document.text or document.title):
                seen.add(key)
                unique_documents.append(document)

        return unique_documents, name, symbol, asset_type, genesis_date, platform

    async def _coingecko(
        self,
        client: httpx.AsyncClient,
        query: str,
    ) -> tuple[list[ResearchDocument], str | None, str | None, str | None, str | None]:
        try:
            search = await client.get("https://api.coingecko.com/api/v3/search", params={"query": query})
            search.raise_for_status()
            coins = search.json().get("coins", [])
            if not coins:
                return [], None, None, None, None
            coin = coins[0]
            coin_id = coin.get("id")
            if not coin_id:
                return [], coin.get("name"), coin.get("symbol", "").upper() or None, None, None
            detail = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{quote(coin_id)}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "false",
                    "community_data": "false",
                    "developer_data": "false",
                    "sparkline": "false",
                },
            )
            detail.raise_for_status()
            data = detail.json()
            description = _clean_text(data.get("description", {}).get("en"), limit=1400)
            homepage = next((url for url in data.get("links", {}).get("homepage", []) if url), "")
            platforms = [key for key, value in data.get("platforms", {}).items() if value]
            platform = ", ".join(platforms[:3]) if platforms else "Native network or exchange-listed market"
            return (
                [
                    ResearchDocument(
                        title=data.get("name") or coin.get("name") or query,
                        source="CoinGecko",
                        url=homepage or f"https://www.coingecko.com/en/coins/{coin_id}",
                        text=description,
                    )
                ],
                data.get("name") or coin.get("name"),
                (data.get("symbol") or coin.get("symbol") or "").upper() or None,
                data.get("genesis_date"),
                platform,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return [], None, None, None, None

    async def _wikipedia(self, client: httpx.AsyncClient, query: str) -> ResearchDocument | None:
        try:
            search = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": query, "format": "json"},
            )
            search.raise_for_status()
            results = search.json().get("query", {}).get("search", [])
            if not results:
                return None
            title = results[0]["title"]
            summary = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}")
            summary.raise_for_status()
            data = summary.json()
            extract = _clean_text(data.get("extract"), limit=1200)
            url = data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{quote(title)}"
            return ResearchDocument(title=title, source="Wikipedia", url=url, text=extract)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None

    async def _duckduckgo(self, client: httpx.AsyncClient, query: str) -> ResearchDocument | None:
        try:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            response.raise_for_status()
            data = response.json()
            abstract = _clean_text(data.get("AbstractText"), limit=900)
            if not abstract:
                return None
            return ResearchDocument(
                title=data.get("Heading") or query,
                source=data.get("AbstractSource") or "DuckDuckGo",
                url=data.get("AbstractURL") or "https://duckduckgo.com/",
                text=abstract,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None

    async def _google_news(self, client: httpx.AsyncClient, query: str) -> list[ResearchDocument]:
        try:
            url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
            response = await client.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            documents: list[ResearchDocument] = []
            for item in root.findall("./channel/item")[:6]:
                title = _clean_text(item.findtext("title"), limit=240)
                link = item.findtext("link") or url
                source = item.findtext("source") or "Google News"
                pub_date = item.findtext("pubDate") or ""
                documents.append(
                    ResearchDocument(
                        title=title,
                        source=source,
                        url=link,
                        text=f"{title}. Published {pub_date}".strip(),
                    )
                )
            return documents
        except (httpx.HTTPError, ET.ParseError):
            return []

    def _build_session_support(self, normalized: str, symbol: str | None, query: str) -> AssetResearchSessionRead:
        candidates = {normalized.upper(), (symbol or "").upper(), query.upper().replace("/", "_").replace("-", "_")}
        candidates = {candidate for candidate in candidates if candidate}
        with SessionLocal() as db:
            latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
            if latest_time is None:
                return AssetResearchSessionRead(
                    matched_symbol=None,
                    dominant_session="Waiting",
                    summary="No market scanner snapshots are available yet.",
                )

            latest_snapshots = db.scalars(
                select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_time)
            ).all()
            match = next(
                (
                    snapshot
                    for snapshot in latest_snapshots
                    if snapshot.symbol.replace("_USDT_PERP", "").upper() in candidates
                    or any(candidate in snapshot.symbol.upper() for candidate in candidates)
                ),
                None,
            )
            if match is None:
                return AssetResearchSessionRead(
                    matched_symbol=None,
                    dominant_session="Not tracked",
                    summary="This asset is not currently matched to a tracked Pionex futures symbol.",
                )

            since = latest_time - timedelta(hours=24)
            snapshots = db.scalars(
                select(models.MarketSnapshot)
                .where(models.MarketSnapshot.symbol == match.symbol)
                .where(models.MarketSnapshot.timestamp >= since)
                .order_by(models.MarketSnapshot.timestamp)
            ).all()

        by_session = {name: {"start": start, "end": end, "deltas": []} for name, start, end in SESSIONS_UTC}
        for previous, current in zip(snapshots, snapshots[1:], strict=False):
            name, _start, _end = _session_name(current.timestamp)
            by_session[name]["deltas"].append(current.price_change_24h - previous.price_change_24h)

        cells: list[MarketSessionMomentumCellRead] = []
        for name, start, end in SESSIONS_UTC:
            deltas = by_session[name]["deltas"]
            net_delta = sum(deltas)
            samples = len(deltas) + 1 if deltas else 0
            cells.append(
                MarketSessionMomentumCellRead(
                    session=name,
                    start_hour_utc=start,
                    end_hour_utc=end,
                    samples=samples,
                    net_delta=round(net_delta, 4),
                    average_5m_delta=round(net_delta / len(deltas), 4) if deltas else 0.0,
                    direction=_direction(net_delta, samples),
                )
            )
        dominant, summary = _session_summary(cells)
        return AssetResearchSessionRead(
            matched_symbol=match.symbol,
            dominant_session=dominant,
            summary=summary,
            latest_change_24h=match.price_change_24h,
            sessions=cells,
        )

    def _build_what(self, documents: list[ResearchDocument], query: str) -> str:
        for source in ("CoinGecko", "Wikipedia", "DuckDuckGo"):
            match = next((document for document in documents if document.source == source and document.text), None)
            if match:
                return match.text[:900]
        return f"No reliable summary was fetched for {query}. Try a more specific symbol or full asset name."

    def _infer_where(self, text: str, asset_type: str) -> str:
        if asset_type == "crypto/token":
            return "Crypto network or token ecosystem; verify the exact chain/contract before trading."
        if re.search(r"\bNASDAQ\b|\bNYSE\b|\bstock exchange\b", text, flags=re.IGNORECASE):
            return "Public equity market or stock exchange context found in public summaries."
        return "No clear home exchange, chain, or operating location was found in the fetched summaries."

    def _risk_notes(self, asset_type: str, documents: list[ResearchDocument]) -> list[str]:
        notes = [
            "This research panel is decision support only, not a buy/sell signal.",
            "Check liquidity, spread, leverage, stop loss, and whether the symbol is actually available on your exchange.",
        ]
        headlines = " ".join(document.title for document in documents)
        if re.search(r"lawsuit|SEC|regulat|hack|exploit|delist|bankrupt", headlines, flags=re.IGNORECASE):
            notes.append("Fetched headlines include legal, regulatory, security, or listing-risk language.")
        if asset_type == "crypto/token":
            notes.append("For tokens, verify contract/network identity to avoid confusing similarly named assets.")
        return notes

    def _what_to_watch_next(self, session: AssetResearchSessionRead) -> list[str]:
        watch = [
            "Whether 24H Change momentum continues to improve or fade in the next 5-minute snapshots.",
            "Fresh news catalysts that agree or conflict with price momentum.",
        ]
        if session.matched_symbol:
            watch.append(f"Whether {session.matched_symbol} keeps the same dominant session pattern.")
        else:
            watch.append("Whether this asset can be matched to a tracked futures symbol before using session support.")
        return watch

    def _summary_text(
        self,
        *,
        name: str,
        symbol: str | None,
        asset_type: str,
        what: str,
        who: str,
        where: str,
        when: str,
        session: AssetResearchSessionRead,
        themes: list[str],
        risks: list[str],
        watch: list[str],
        confidence: float,
    ) -> str:
        lines = [
            f"Research brief: {name}{f' ({symbol})' if symbol else ''}",
            f"Asset type: {asset_type}",
            "",
            f"What: {what}",
            f"Who: {who}",
            f"Where: {where}",
            f"When: {when}",
            "",
                f"Session pressure read: {session.dominant_session}",
                session.summary,
        ]
        if session.latest_change_24h is not None:
            lines.append(f"Latest tracked 24H Change: {session.latest_change_24h:+.2f}%")
        lines.extend(
            [
                "",
                "Recent themes: " + "; ".join(themes),
                "Risks: " + "; ".join(risks),
                "What to watch next: " + "; ".join(watch),
                "",
                f"Research confidence: {confidence:.0%} based on fetched source count and whether session data matched.",
            ]
        )
        return "\n".join(lines)
