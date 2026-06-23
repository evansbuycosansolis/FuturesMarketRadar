from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from ..config import Settings
from .pionex_client import PionexSymbolInfo, PionexTicker


class PionexChromiumScraperError(RuntimeError):
    pass


@dataclass(slots=True)
class ScrapedMarketBoard:
    symbols: list[PionexSymbolInfo]
    tickers: list[PionexTicker]


def _merge_boards(*boards: ScrapedMarketBoard) -> ScrapedMarketBoard:
    symbols: dict[str, PionexSymbolInfo] = {}
    tickers: dict[str, PionexTicker] = {}
    for board in boards:
        for symbol in board.symbols:
            symbols[symbol.symbol] = symbol
        for ticker in board.tickers:
            tickers[ticker.symbol] = ticker
    return ScrapedMarketBoard(symbols=list(symbols.values()), tickers=list(tickers.values()))


def _parse_float(value: str) -> float:
    cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
    if cleaned in {"", "--"}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_volume(value: str) -> float:
    cleaned = value.replace("$", "").replace(",", "").strip().upper()
    if cleaned in {"", "--"}:
        return 0.0
    multiplier = 1.0
    if cleaned.endswith("K"):
        multiplier = 1_000.0
        cleaned = cleaned[:-1]
    elif cleaned.endswith("M"):
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]
    elif cleaned.endswith("B"):
        multiplier = 1_000_000_000.0
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return 0.0


def _looks_like_number(value: str) -> bool:
    return bool(re.fullmatch(r"\$?[\d,]+(?:\.\d+)?|--", value.strip()))


def _normalize_symbol(value: str) -> str:
    return re.sub(r"\s+", "", value.strip()).upper()


def _parse_table_text(text: str, limit: int) -> ScrapedMarketBoard:
    marker = "24H Change"
    start = text.find(marker)
    if start < 0:
        raise PionexChromiumScraperError("Could not find the Pionex market table in Chromium output.")

    lines = [
        line.strip()
        for line in text[start + len(marker):].splitlines()
        if line.strip() and line.strip() not in {"Pair", "Price", "Fiat price(USD)", "24H Volume", "24H Change"}
    ]
    symbols: list[PionexSymbolInfo] = []
    tickers: list[PionexTicker] = []
    i = 0
    while i < len(lines) - 5 and len(tickers) < limit:
        if lines[i] in {"Join the Community", "Community", "About"}:
            break
        if i + 2 >= len(lines) or lines[i + 1] != "/USDT" or lines[i + 2] != "Perp":
            i += 1
            continue

        base_asset = _normalize_symbol(lines[i])
        i += 3
        while i < len(lines) and not _looks_like_number(lines[i]):
            i += 1
        if i + 3 >= len(lines):
            break

        price = _parse_float(lines[i])
        quote_volume = _parse_volume(lines[i + 2])
        change = _parse_float(lines[i + 3])
        if price <= 0:
            i += 4
            continue

        symbol = f"{base_asset}_USDT_PERP"
        open_price = price / (1 + change / 100) if change > -99.99 else price
        base_volume = quote_volume / price if price else 0.0
        symbols.append(
            PionexSymbolInfo(
                symbol=symbol,
                name=base_asset,
                base_currency=base_asset,
                quote_currency="USDT",
                market_type="PERP",
                status="TRADING",
            )
        )
        tickers.append(
            PionexTicker(
                symbol=symbol,
                time=0,
                open=open_price,
                close=price,
                high=price,
                low=price,
                volume=base_volume,
                amount=quote_volume,
                count=0,
            )
        )
        i += 4

    if not tickers:
        raise PionexChromiumScraperError("Chromium loaded Pionex, but no market rows were parsed.")
    return ScrapedMarketBoard(symbols=symbols, tickers=tickers)


class PionexChromiumScraper:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def scrape_futures_gainers(self) -> ScrapedMarketBoard:
        executable_path = self._settings.chromium_executable_path
        if executable_path and not Path(executable_path).exists():
            raise PionexChromiumScraperError(f"Chrome executable was not found at {executable_path}.")

        timeout_ms = int(self._settings.chromium_market_timeout_seconds * 1000)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=executable_path or None,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1500, "height": 3600},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                    ),
                )
                page.set_default_timeout(timeout_ms)
                await page.goto(self._settings.chromium_market_url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(8000)
                await page.get_by_text("24H Change", exact=True).click()
                await page.wait_for_timeout(3000)
                text = await page.locator("body").inner_text(timeout=timeout_ms)
                return _parse_table_text(text, self._settings.chromium_market_row_limit)
            except PlaywrightTimeoutError as exc:
                raise PionexChromiumScraperError(f"Chromium timed out while reading Pionex: {exc}") from exc
            finally:
                await browser.close()

    async def scrape_futures_movers(self) -> ScrapedMarketBoard:
        executable_path = self._settings.chromium_executable_path
        if executable_path and not Path(executable_path).exists():
            raise PionexChromiumScraperError(f"Chrome executable was not found at {executable_path}.")

        timeout_ms = int(self._settings.chromium_market_timeout_seconds * 1000)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=executable_path or None,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1500, "height": 3600},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                    ),
                )
                page.set_default_timeout(timeout_ms)
                await page.goto(self._settings.chromium_market_url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(8000)
                change_header = page.get_by_text("24H Change", exact=True)
                await change_header.click()
                await page.wait_for_timeout(3000)
                gainers = _parse_table_text(await page.locator("body").inner_text(timeout=timeout_ms), self._settings.chromium_market_row_limit)
                await change_header.click()
                await page.wait_for_timeout(3000)
                losers = _parse_table_text(await page.locator("body").inner_text(timeout=timeout_ms), self._settings.chromium_market_row_limit)
                return _merge_boards(gainers, losers)
            except PlaywrightTimeoutError as exc:
                raise PionexChromiumScraperError(f"Chromium timed out while reading Pionex movers: {exc}") from exc
            finally:
                await browser.close()
