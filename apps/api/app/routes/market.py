from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from ..config import get_settings
from ..db import SessionLocal
from .. import models
from ..schemas import (
    MarketChangeMomentumRead,
    MarketChangeTrajectoryResponse,
    FuturesAnomalyRead,
    FuturesAnomalyResponse,
    MarketOverviewResponse,
    MarketQualityCheckRead,
    MarketQualityResponse,
    MarketSessionMomentumCellRead,
    MarketSessionMomentumRead,
    MarketSessionMomentumResponse,
    OneHourSpikeRead,
    OneHourSpikeResponse,
    ScoreEntry,
    SleepingGiantResponse,
    SleepingGiantSetupRead,
    SymbolListResponse,
    SymbolRead,
)
from ..services.anomaly_scanner import scan_futures_anomalies
from ..services.binance_futures_client import BinanceFuturesClient
from ..services.one_hour_spike_scanner import scan_one_hour_spikes
from ..services.pionex_client import PionexKline
from ..services.report_service import models_to_score_entry
from ..services.sleeping_giant_scanner import RecentAwakeningScanner, SleepingGiantConfig, SleepingGiantScanner


router = APIRouter(tags=["market"])
settings = get_settings()
STALE_MARKET_MINUTES = 10
RECOVERY_MAX_LATEST_CHANGE = 20.0
RECOVERY_START_THRESHOLD = 2.0
FADE_HIGH_WATERMARK = 40.0
SLEEPING_GIANT_CACHE_SECONDS = 240
ONE_HOUR_SPIKE_CACHE_SECONDS = 240

SESSIONS_UTC = [
    ("Asian", 23, 7),
    ("London", 7, 15),
    ("New York", 15, 23),
]
_SLEEPING_GIANT_CACHE: dict[tuple[int, int, int, str, str, int], tuple[datetime, SleepingGiantResponse]] = {}
_ONE_HOUR_SPIKE_CACHE: dict[tuple[int, int, int], tuple[datetime, OneHourSpikeResponse]] = {}


def _latest_report_time(db) -> object:
    return db.scalar(select(func.max(models.CoinScore.report_time)))


def _load_scores(db, latest_time, score_column, limit: int) -> list[ScoreEntry]:
    if latest_time is None:
        raise HTTPException(status_code=404, detail="No scan results are available yet.")

    snapshots = {
        snapshot.symbol: snapshot
        for snapshot in db.scalars(
            select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_time)
        ).all()
    }
    scores = db.scalars(
        select(models.CoinScore)
        .where(models.CoinScore.report_time == latest_time)
        .order_by(desc(score_column))
        .limit(limit)
    ).all()
    return [models_to_score_entry(score, snapshots.get(score.symbol)) for score in scores]


def _latest_score_entries(db, latest_time) -> list[ScoreEntry]:
    if latest_time is None:
        raise HTTPException(status_code=404, detail="No scan results are available yet.")

    snapshots = {
        snapshot.symbol: snapshot
        for snapshot in db.scalars(
            select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_time)
        ).all()
    }
    scores = db.scalars(
        select(models.CoinScore).where(models.CoinScore.report_time == latest_time)
    ).all()
    return [models_to_score_entry(score, snapshots.get(score.symbol)) for score in scores]


def _snapshot_to_score_entry(snapshot: models.MarketSnapshot, score: models.CoinScore | None = None) -> ScoreEntry:
    activity_score = min(100.0, max(0.0, snapshot.quote_volume_24h / 1_000_000))
    return ScoreEntry(
        symbol=snapshot.symbol,
        price=snapshot.price,
        price_change_24h=snapshot.price_change_24h,
        volume_24h=snapshot.volume_24h,
        quote_volume_24h=snapshot.quote_volume_24h,
        high_24h=snapshot.high_24h,
        low_24h=snapshot.low_24h,
        open_interest=snapshot.open_interest,
        open_interest_change_pct=score.open_interest_change_pct if score else 0.0,
        activity_score=score.activity_score if score else activity_score,
        bullish_score=score.bullish_score if score else max(snapshot.price_change_24h, 0.0),
        bearish_score=score.bearish_score if score else max(-snapshot.price_change_24h, 0.0),
        buyer_absence_score=score.buyer_absence_score if score else 0.0,
        dead_market_score=score.dead_market_score if score else 0.0,
        quiet_rally_score=score.quiet_rally_score if score else 0.0,
        volume_spike_ratio=score.volume_spike_ratio if score else 0.0,
        price_change_5m=score.price_change_5m if score else 0.0,
        price_change_15m=score.price_change_15m if score else 0.0,
        atr_percent=score.atr_percent if score else 0.0,
        buyer_volume_share=score.buyer_volume_share if score else 0.0,
        green_candle_ratio=score.green_candle_ratio if score else 0.0,
        trend_label=score.trend_label if score else "Market board only",
        breakdown=score.score_breakdown_json if score and score.score_breakdown_json else {},
    )


def _latest_market_entries(db, latest_time) -> list[ScoreEntry]:
    if latest_time is None:
        raise HTTPException(status_code=404, detail="No scan results are available yet.")

    scores = {
        score.symbol: score
        for score in db.scalars(
            select(models.CoinScore).where(models.CoinScore.report_time == latest_time)
        ).all()
    }
    snapshots = db.scalars(
        select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_time)
    ).all()
    return [_snapshot_to_score_entry(snapshot, scores.get(snapshot.symbol)) for snapshot in snapshots]


def _market_freshness(latest_time) -> tuple[float | None, bool, str | None]:
    if latest_time is None:
        return None, True, "No market snapshot is available yet."
    normalized = latest_time if getattr(latest_time, "tzinfo", None) else latest_time.replace(tzinfo=timezone.utc)
    age_minutes = max(0.0, (datetime.now(timezone.utc) - normalized.astimezone(timezone.utc)).total_seconds() / 60)
    if age_minutes > STALE_MARKET_MINUTES:
        return (
            round(age_minutes, 1),
            True,
            f"Market data is stale: latest successful snapshot is {age_minutes:.1f} minutes old.",
        )
    return round(age_minutes, 1), False, None


def _quality_status(checks: list[MarketQualityCheckRead]) -> tuple[str, float]:
    if any(check.status == "fail" for check in checks):
        status = "unavailable"
    elif any(check.status == "warn" for check in checks):
        status = "degraded"
    else:
        status = "healthy"
    score = 100.0
    for check in checks:
        if check.status == "warn":
            score -= 15
        elif check.status == "fail":
            score -= 35
    return status, max(0.0, score)


def _session_name(timestamp) -> tuple[str, int, int]:
    normalized = timestamp
    if getattr(normalized, "tzinfo", None) is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    hour = normalized.astimezone(timezone.utc).hour
    for name, start_hour, end_hour in SESSIONS_UTC:
        if start_hour <= end_hour and start_hour <= hour < end_hour:
            return name, start_hour, end_hour
        if start_hour > end_hour and (hour >= start_hour or hour < end_hour):
            return name, start_hour, end_hour
    return "New York", 15, 23


def _direction(delta: float, samples: int) -> str:
    if samples < 1:
        return "insufficient"
    if delta >= 0.15:
        return "up"
    if delta <= -0.15:
        return "down"
    return "flat"


def _change_direction(delta: float | None, samples: int) -> str:
    if samples < 2 or delta is None:
        return "new"
    if delta >= 0.25:
        return "increasing"
    if delta <= -0.25:
        return "decreasing"
    return "flat"


def _change_strength(delta: float | None) -> str:
    if delta is None:
        return "none"
    absolute = abs(delta)
    if absolute >= 10:
        return "strong"
    if absolute >= 3:
        return "moderate"
    if absolute >= 0.25:
        return "weak"
    return "none"


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100


def _snapshot_quality(
    history: list[models.MarketSnapshot],
    expected_samples: int | None,
) -> tuple[float | None, float | None, str]:
    if not history:
        return None, None, "thin"

    coverage = None
    if expected_samples and expected_samples > 0:
        coverage = min((len(history) / expected_samples) * 100, 100.0)

    gaps = [
        (current.timestamp - previous.timestamp).total_seconds() / 60
        for previous, current in zip(history, history[1:], strict=False)
    ]
    max_gap = max(gaps) if gaps else None

    if coverage is not None and coverage >= 75 and (max_gap is None or max_gap <= 12):
        quality = "strong"
    elif coverage is not None and coverage >= 40 and (max_gap is None or max_gap <= 30):
        quality = "partial"
    else:
        quality = "thin"
    return (
        round(coverage, 2) if coverage is not None else None,
        round(max_gap, 2) if max_gap is not None else None,
        quality,
    )


def _session_summary(cells: list[MarketSessionMomentumCellRead]) -> tuple[str, str]:
    valid_cells = [cell for cell in cells if cell.samples >= 2]
    if not valid_cells:
        return "Waiting", "Not enough stored 5-minute snapshots yet."

    strongest = max(valid_cells, key=lambda cell: abs(cell.net_delta))
    strongest_bias = "buying pressure" if strongest.net_delta > 0 else "selling pressure" if strongest.net_delta < 0 else "balanced flow"
    readable = {
        "up": "buying pressure",
        "down": "selling pressure",
        "flat": "balanced/flat",
        "insufficient": "thin data",
    }
    parts = [
        f"{cell.session}: {readable[cell.direction]} ({cell.net_delta:+.2f} pts)"
        for cell in cells
        if cell.samples >= 2
    ]
    return strongest.session, f"{strongest.session} shows strongest {strongest_bias} ({strongest.net_delta:+.2f} pts). " + "; ".join(parts)


def _session_cells_for_history(history: list[models.MarketSnapshot]) -> tuple[str, str, list[MarketSessionMomentumCellRead]]:
    by_session = {
        name: {"start": start, "end": end, "deltas": []}
        for name, start, end in SESSIONS_UTC
    }
    for previous, current in zip(history, history[1:], strict=False):
        name, _start, _end = _session_name(current.timestamp)
        by_session[name]["deltas"].append(current.price_change_24h - previous.price_change_24h)

    cells: list[MarketSessionMomentumCellRead] = []
    for name, start, end in SESSIONS_UTC:
        deltas = by_session[name]["deltas"]
        net_delta = sum(deltas)
        average_delta = net_delta / len(deltas) if deltas else 0.0
        samples = len(deltas)
        cells.append(
            MarketSessionMomentumCellRead(
                session=name,
                start_hour_utc=start,
                end_hour_utc=end,
                samples=samples,
                net_delta=round(net_delta, 4),
                average_5m_delta=round(average_delta, 4),
                direction=_direction(net_delta, samples),
            )
        )
    dominant_session, summary = _session_summary(cells)
    return dominant_session, summary, cells


def _build_change_momentum_item(
    symbol: str,
    history: list[models.MarketSnapshot],
    *,
    anchor: str = "earliest",
    expected_samples: int | None = None,
) -> MarketChangeMomentumRead | None:
    if not history:
        return None
    latest = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    if anchor == "trough":
        anchor_snapshot = min(history, key=lambda snapshot: snapshot.price_change_24h)
    elif anchor == "peak":
        anchor_snapshot = max(history, key=lambda snapshot: snapshot.price_change_24h)
    else:
        anchor_snapshot = history[0]
    delta_5m = latest.price_change_24h - previous.price_change_24h if previous else None
    delta_window = latest.price_change_24h - anchor_snapshot.price_change_24h if len(history) >= 2 else None
    price_delta_5m_pct = _pct_change(latest.price, previous.price) if previous else None
    price_delta_window_pct = _pct_change(latest.price, anchor_snapshot.price) if len(history) >= 2 else None
    sample_coverage_pct, max_gap_minutes, data_quality = _snapshot_quality(history, expected_samples)
    dominant_session, session_summary, sessions = _session_cells_for_history(history)
    return MarketChangeMomentumRead(
        symbol=symbol,
        price=latest.price,
        anchor_price=anchor_snapshot.price if len(history) >= 2 else None,
        latest_change_24h=round(latest.price_change_24h, 4),
        previous_change_24h=round(anchor_snapshot.price_change_24h, 4),
        delta_5m=round(delta_5m, 4) if delta_5m is not None else None,
        delta_window=round(delta_window, 4) if delta_window is not None else None,
        price_delta_5m_pct=round(price_delta_5m_pct, 4) if price_delta_5m_pct is not None else None,
        price_delta_window_pct=round(price_delta_window_pct, 4) if price_delta_window_pct is not None else None,
        samples=len(history),
        expected_samples=expected_samples,
        sample_coverage_pct=sample_coverage_pct,
        max_gap_minutes=max_gap_minutes,
        data_quality=data_quality,
        direction=_change_direction(delta_window, len(history)),
        strength=_change_strength(delta_window),
        sparkline=[round(snapshot.price_change_24h, 4) for snapshot in history[-18:]],
        latest_timestamp=latest.timestamp,
        previous_timestamp=anchor_snapshot.timestamp if len(history) >= 2 else None,
        dominant_session=dominant_session,
        session_summary=session_summary,
        sessions=sessions,
    )


def _timestamp_to_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _bucket_start(timestamp: datetime, hours: int = 4) -> datetime:
    normalized = _timestamp_to_utc(timestamp)
    bucket_hour = (normalized.hour // hours) * hours
    return normalized.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)


def _snapshots_to_candles(snapshots: list[models.MarketSnapshot], *, hours: int = 4) -> list[PionexKline]:
    candles: list[PionexKline] = []
    bucket: list[models.MarketSnapshot] = []
    current_bucket: datetime | None = None

    for snapshot in sorted(snapshots, key=lambda item: item.timestamp):
        bucket_start = _bucket_start(snapshot.timestamp, hours=hours)
        if current_bucket is None:
            current_bucket = bucket_start
        if bucket_start != current_bucket and bucket:
            candles.append(_bucket_to_candle(current_bucket, bucket))
            bucket = []
            current_bucket = bucket_start
        bucket.append(snapshot)

    if current_bucket is not None and bucket:
        candles.append(_bucket_to_candle(current_bucket, bucket))

    return candles


def _bucket_to_candle(bucket_start: datetime, snapshots: list[models.MarketSnapshot]) -> PionexKline:
    ordered = sorted(snapshots, key=lambda item: item.timestamp)
    open_price = ordered[0].price
    close_price = ordered[-1].price
    high = max(snapshot.price for snapshot in ordered)
    low = min(snapshot.price for snapshot in ordered)
    quote_volumes = [snapshot.quote_volume_24h for snapshot in ordered]
    volume_proxy = max(max(quote_volumes) - min(quote_volumes), 0.0)
    if volume_proxy <= 0:
        volume_proxy = sum(quote_volumes) / max(len(quote_volumes), 1)
    return PionexKline(
        time=int(bucket_start.timestamp() * 1000),
        open=open_price,
        close=close_price,
        high=high,
        low=low,
        volume=volume_proxy,
    )


def _price_relevance_multiplier(snapshot_price: float | None, candle_price: float | None) -> float:
    if snapshot_price is None or candle_price is None or snapshot_price <= 0:
        return 0.75
    difference_pct = abs(snapshot_price - candle_price) / snapshot_price * 100
    if difference_pct <= 0.75:
        return 1.0
    if difference_pct <= 2.0:
        return 0.9
    if difference_pct <= 5.0:
        return 0.75
    return 0.55


@router.get("/symbols", response_model=SymbolListResponse)
def list_symbols(
    quote_asset: str | None = Query(default=None),
    status: str | None = Query(default="TRADING"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> SymbolListResponse:
    with SessionLocal() as db:
        query = select(models.Symbol).order_by(models.Symbol.quote_asset, models.Symbol.symbol)
        if quote_asset:
            query = query.where(models.Symbol.quote_asset == quote_asset.upper())
        if status:
            query = query.where(models.Symbol.status == status.upper())
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = db.scalars(query.limit(limit)).all()

    return SymbolListResponse(total=int(total), items=[SymbolRead.model_validate(item) for item in items])


@router.get("/market/overview", response_model=MarketOverviewResponse)
def market_overview(limit: int = Query(default=80, ge=10, le=250)) -> MarketOverviewResponse:
    with SessionLocal() as db:
        latest_snapshot_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        entries = _latest_market_entries(db, latest_snapshot_time)

    coin_cap = sorted(entries, key=lambda entry: entry.quote_volume_24h, reverse=True)[:10]

    gainers = sorted(entries, key=lambda entry: entry.price_change_24h, reverse=True)[:10]
    losers = sorted(entries, key=lambda entry: entry.price_change_24h)[:10]
    futures = sorted(
        entries,
        key=lambda entry: (entry.price_change_24h, entry.activity_score, entry.quote_volume_24h),
        reverse=True,
    )[:limit]
    latest_age_minutes, is_stale, data_warning = _market_freshness(latest_snapshot_time)

    return MarketOverviewResponse(
        latest_report_at=latest_snapshot_time,
        latest_age_minutes=latest_age_minutes,
        is_stale=is_stale,
        data_source=f"pionex-{settings.market_data_source} snapshot",
        data_warning=data_warning,
        coin_cap=coin_cap,
        gainers=gainers,
        losers=losers,
        futures=futures,
    )


@router.get("/market/quality", response_model=MarketQualityResponse)
def market_quality() -> MarketQualityResponse:
    with SessionLocal() as db:
        latest_snapshot_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        latest_score_time = db.scalar(select(func.max(models.CoinScore.report_time)))
        snapshot_count = (
            db.scalar(
                select(func.count())
                .select_from(models.MarketSnapshot)
                .where(models.MarketSnapshot.timestamp == latest_snapshot_time)
            )
            if latest_snapshot_time
            else 0
        ) or 0
        score_count = (
            db.scalar(
                select(func.count())
                .select_from(models.CoinScore)
                .where(models.CoinScore.report_time == latest_score_time)
            )
            if latest_score_time
            else 0
        ) or 0

    age_minutes, is_stale, warning = _market_freshness(latest_snapshot_time)
    checks: list[MarketQualityCheckRead] = [
        MarketQualityCheckRead(
            name="Market freshness",
            status="fail" if latest_snapshot_time is None else "warn" if is_stale else "pass",
            detail=warning or f"Latest market snapshot is {age_minutes:.1f} minutes old.",
            metric=age_minutes,
            threshold=STALE_MARKET_MINUTES,
        ),
        MarketQualityCheckRead(
            name="Pionex board coverage",
            status="pass" if snapshot_count >= 50 else "warn" if snapshot_count >= 20 else "fail",
            detail=f"{snapshot_count} futures rows were captured in the latest market snapshot.",
            metric=float(snapshot_count),
            threshold=50.0,
        ),
        MarketQualityCheckRead(
            name="Scanner score coverage",
            status="pass" if score_count >= 40 else "warn" if score_count >= 10 else "fail",
            detail=f"{score_count} symbols have computed scanner scores in the latest scoring run.",
            metric=float(score_count),
            threshold=40.0,
        ),
    ]
    status, score = _quality_status(checks)
    return MarketQualityResponse(
        status=status,
        score=round(score, 1),
        latest_report_at=latest_snapshot_time,
        source=f"pionex-{settings.market_data_source} snapshot + Binance USD-M candles for overlapping Sleeping Giant symbols",
        checks=checks,
        caveats=[
            "Market board values come from Pionex page capture and can break if Pionex changes page markup.",
            "Sleeping Giant analysis uses Binance USD-M Futures candles for overlapping symbols, so it may differ from exact Pionex pricing.",
            "Signals are decision support only; they need chart confirmation, risk checks, and user judgment.",
            "No strategy is trustworthy until it has backtests, forward tracking, and false-positive/false-negative review.",
        ],
    )


@router.get("/market/futures-anomalies", response_model=FuturesAnomalyResponse)
def futures_anomalies(
    limit: int = Query(default=12, ge=1, le=50),
    lookback_hours: int = Query(default=24, ge=2, le=72),
    max_symbols: int = Query(default=80, ge=20, le=200),
) -> FuturesAnomalyResponse:
    with SessionLocal() as db:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No market snapshots are available yet.")
        latest_entries = _latest_market_entries(db, latest_time)
        ranked_symbols = [
            entry.symbol
            for entry in sorted(latest_entries, key=lambda entry: entry.quote_volume_24h, reverse=True)[:max_symbols]
        ]
        since = latest_time - timedelta(hours=lookback_hours)
        snapshots = db.scalars(
            select(models.MarketSnapshot)
            .where(models.MarketSnapshot.symbol.in_(ranked_symbols))
            .where(models.MarketSnapshot.timestamp >= since)
            .order_by(models.MarketSnapshot.symbol, models.MarketSnapshot.timestamp)
        ).all()

    histories: dict[str, list[models.MarketSnapshot]] = {symbol: [] for symbol in ranked_symbols}
    for snapshot in snapshots:
        histories.setdefault(snapshot.symbol, []).append(snapshot)

    breakouts, breakdowns = scan_futures_anomalies(
        histories,
        limit=limit,
        min_quote_volume=settings.scanner_min_quote_volume,
    )

    return FuturesAnomalyResponse(
        latest_report_at=latest_time,
        interval_seconds=300,
        lookback_hours=lookback_hours,
        source=f"pionex-{settings.market_data_source} snapshot anomaly layer",
        top_breakouts=[FuturesAnomalyRead(**asdict(candidate)) for candidate in breakouts],
        top_breakdowns=[FuturesAnomalyRead(**asdict(candidate)) for candidate in breakdowns],
        note=(
            "Decision-support anomaly ranking only. It normalizes price movement by recent volatility, checks volume expansion, "
            "acceleration, isolation versus BTC/ETH context, liquidity, and available open-interest change. Current feed cadence "
            "is stored market snapshots, so 1m/1s fields are approximations until a faster live feed is connected."
        ),
    )


@router.get("/market/one-hour-spikes", response_model=OneHourSpikeResponse)
async def one_hour_spikes(
    limit: int = Query(default=20, ge=1, le=60),
    max_symbols: int = Query(default=160, ge=20, le=250),
    baseline_candles: int = Query(default=48, ge=24, le=120),
) -> OneHourSpikeResponse:
    cache_key = (limit, max_symbols, baseline_candles)
    cached = _ONE_HOUR_SPIKE_CACHE.get(cache_key)
    if cached:
        cached_at, cached_response = cached
        if (datetime.now(timezone.utc) - cached_at).total_seconds() <= ONE_HOUR_SPIKE_CACHE_SECONDS:
            return cached_response

    with SessionLocal() as db:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No market snapshots are available yet.")
        latest_entries = _latest_market_entries(db, latest_time)
        ranked_symbols = [
            entry.symbol
            for entry in sorted(latest_entries, key=lambda entry: entry.quote_volume_24h, reverse=True)[:max_symbols]
        ]
        latest_snapshot_prices = {entry.symbol: entry.price for entry in latest_entries}

    binance_client = BinanceFuturesClient(settings)
    try:
        candles_by_symbol = await binance_client.get_klines_for_pionex_symbols(
            ranked_symbols,
            interval="1h",
            limit=baseline_candles + 4,
            max_concurrency=10,
        )
    finally:
        await binance_client.close()

    raw_candidates = scan_one_hour_spikes(
        candles_by_symbol,
        limit=limit,
        baseline_candles=baseline_candles,
    )
    response = OneHourSpikeResponse(
        latest_report_at=latest_time,
        interval_seconds=300,
        baseline_candles=baseline_candles,
        scanned_symbols=len(candles_by_symbol),
        candidates=[
            OneHourSpikeRead(
                symbol=item.symbol,
                direction="bullish" if item.direction == "bullish" else "bearish",
                score=item.score,
                current_price=latest_snapshot_prices.get(item.symbol, item.current_price),
                latest_price_change_pct=item.latest_price_change_pct,
                latest_range_pct=item.latest_range_pct,
                baseline_range_pct=item.baseline_range_pct,
                range_ratio=item.range_ratio,
                volume_ratio=item.volume_ratio,
                latest_volume=item.latest_volume,
                baseline_volume=item.baseline_volume,
                timestamp=datetime.fromtimestamp(item.timestamp / 1000, tz=timezone.utc) if item.timestamp else None,
                reason_tags=item.reason_tags,
            )
            for item in raw_candidates
        ],
        source="Binance USD-M 1H candles for Pionex-overlapping futures symbols",
        note=(
            "Simple 1H spike monitor. It scans tracked Pionex futures symbols on the 5-minute refresh cadence, "
            "then flags the latest closed 1H candle when both price range/change and volume are abnormal versus the recent median baseline. "
            "Decision support only; not a buy/sell signal."
        ),
    )
    _ONE_HOUR_SPIKE_CACHE[cache_key] = (datetime.now(timezone.utc), response)
    return response


@router.get("/market/session-momentum", response_model=MarketSessionMomentumResponse)
def session_momentum(
    limit: int = Query(default=40, ge=5, le=120),
    lookback_hours: int = Query(default=24, ge=8, le=72),
) -> MarketSessionMomentumResponse:
    with SessionLocal() as db:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No scan results are available yet.")
        latest_entries = _latest_market_entries(db, latest_time)
        ranked_entries = sorted(
            latest_entries,
            key=lambda entry: (abs(entry.price_change_24h), entry.activity_score, entry.quote_volume_24h),
            reverse=True,
        )[:limit]
        ranked_symbols = [entry.symbol for entry in ranked_entries]
        latest_by_symbol = {entry.symbol: entry for entry in ranked_entries}
        since = latest_time - timedelta(hours=lookback_hours)
        snapshots = db.scalars(
            select(models.MarketSnapshot)
            .where(models.MarketSnapshot.symbol.in_(ranked_symbols))
            .where(models.MarketSnapshot.timestamp >= since)
            .order_by(models.MarketSnapshot.symbol, models.MarketSnapshot.timestamp)
        ).all()

    history: dict[str, list[models.MarketSnapshot]] = {symbol: [] for symbol in ranked_symbols}
    for snapshot in snapshots:
        history.setdefault(snapshot.symbol, []).append(snapshot)

    items: list[MarketSessionMomentumRead] = []
    for symbol in ranked_symbols:
        symbol_history = history.get(symbol, [])
        dominant_session, summary, cells = _session_cells_for_history(symbol_history)
        latest = latest_by_symbol[symbol]
        items.append(
            MarketSessionMomentumRead(
                symbol=symbol,
                price=latest.price,
                latest_change_24h=latest.price_change_24h,
                dominant_session=dominant_session,
                summary=summary,
                sessions=cells,
            )
        )

    items.sort(
        key=lambda item: max((abs(cell.net_delta) for cell in item.sessions), default=0.0),
        reverse=True,
    )
    return MarketSessionMomentumResponse(
        latest_report_at=latest_time,
        lookback_hours=lookback_hours,
        interval_minutes=5,
        note="Computed from stored 24H Change snapshots only; no extra Pionex pull is made for this section.",
        items=items,
    )


@router.get("/market/change-trajectory", response_model=MarketChangeTrajectoryResponse)
def change_trajectory(
    limit: int = Query(default=20, ge=5, le=60),
    lookback_hours: int = Query(default=8, ge=1, le=48),
) -> MarketChangeTrajectoryResponse:
    with SessionLocal() as db:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No scan results are available yet.")
        since = latest_time - timedelta(hours=lookback_hours)
        latest_entries = _latest_market_entries(db, latest_time)
        ranked_symbols = [
            entry.symbol
            for entry in sorted(
                latest_entries,
                key=lambda entry: (entry.quote_volume_24h, abs(entry.price_change_24h)),
                reverse=True,
            )
        ]
        snapshots = db.scalars(
            select(models.MarketSnapshot)
            .where(models.MarketSnapshot.symbol.in_(ranked_symbols))
            .where(models.MarketSnapshot.timestamp >= since)
            .order_by(models.MarketSnapshot.symbol, models.MarketSnapshot.timestamp)
        ).all()

    history: dict[str, list[models.MarketSnapshot]] = {symbol: [] for symbol in ranked_symbols}
    for snapshot in snapshots:
        history.setdefault(snapshot.symbol, []).append(snapshot)

    recovery_items: list[MarketChangeMomentumRead] = []
    fade_items: list[MarketChangeMomentumRead] = []
    expected_samples = int((lookback_hours * 60) / 5) + 1
    for symbol in ranked_symbols:
        symbol_history = history.get(symbol, [])
        if len(symbol_history) < 2:
            continue
        latest = symbol_history[-1]
        trough = min(snapshot.price_change_24h for snapshot in symbol_history)
        peak = max(snapshot.price_change_24h for snapshot in symbol_history)

        recovery = _build_change_momentum_item(symbol, symbol_history, anchor="trough", expected_samples=expected_samples)
        if (
            recovery
            and recovery.delta_window is not None
            and recovery.delta_window > 0.25
            and trough <= RECOVERY_START_THRESHOLD
            and latest.price_change_24h <= RECOVERY_MAX_LATEST_CHANGE
        ):
            recovery_items.append(recovery)

        fade = _build_change_momentum_item(symbol, symbol_history, anchor="peak", expected_samples=expected_samples)
        if (
            fade
            and fade.delta_window is not None
            and fade.delta_window < -0.25
            and peak >= FADE_HIGH_WATERMARK
        ):
            fade_items.append(fade)

    improving = sorted(
        recovery_items,
        key=lambda item: (item.delta_window or 0.0, -abs(item.latest_change_24h)),
        reverse=True,
    )[:limit]
    fading = sorted(
        fade_items,
        key=lambda item: (item.delta_window or 0.0, item.latest_change_24h),
    )[:limit]

    return MarketChangeTrajectoryResponse(
        latest_report_at=latest_time,
        lookback_hours=lookback_hours,
        interval_minutes=5,
        improving=improving,
        fading=fading,
        note=(
            "Computed from stored Pionex-board 24H Change snapshots, with snapshot-price context and capture-quality checks. "
            "This is rolling 24H Change momentum, not OHLC candle momentum. Recovery candidates started from negative/near-zero readings and are improving "
            f"without already exceeding +{RECOVERY_MAX_LATEST_CHANGE:.0f}%. Fade candidates previously reached at least "
            f"+{FADE_HIGH_WATERMARK:.0f}% and are now cooling down from that high-watermark."
        ),
    )


@router.get("/market/sleeping-giants", response_model=SleepingGiantResponse)
async def sleeping_giants(
    limit: int = Query(default=12, ge=1, le=50),
    lookback_days: int = Query(default=21, ge=7, le=60),
    max_symbols: int = Query(default=80, ge=20, le=200),
    timeframe: str = Query(default="1H", pattern="^(1H|4H|1h|4h)$"),
    mode: str = Query(default="strict", pattern="^(strict|recent)$"),
) -> SleepingGiantResponse:
    timeframe = timeframe.upper()
    mode = mode.lower()
    baseline_candles = 362 if mode == "recent" and timeframe == "1H" else 200
    if timeframe == "4H":
        candle_interval = "4h"
        candle_hours = 4
        compression_min_candles = 80
        compression_max_candles = baseline_candles
        candle_limit = min(max((lookback_days * 6) + 10, baseline_candles + 10), 300)
        note_detail = "It requires the prior 200 closed 4H candles to stay sleeping, then the alarm candle and confirmation candle must both be at least 2x the median candle height."
    else:
        candle_interval = "1h"
        candle_hours = 1
        compression_min_candles = 80 if mode == "strict" else 50
        compression_max_candles = baseline_candles
        candle_limit = min(max((lookback_days * 24) + 10, baseline_candles + 10), 600)
        if mode == "recent":
            note_detail = (
                "Recent-awakening mode uses the broader 362 closed 1H candle baseline and surfaces symbols whose latest activity already started to expand. "
                "It does not require the full baseline to remain asleep, so it is noisier than the strict alarm-confirmation scanner."
            )
        else:
            note_detail = "It requires the prior 200 closed 1H candles to stay sleeping, then the alarm candle and confirmation candle must both be at least 2x the median candle height."
    required_candles = baseline_candles + 2
    cache_key = (limit, lookback_days, max_symbols, timeframe, mode, required_candles)
    cached = _SLEEPING_GIANT_CACHE.get(cache_key)
    if cached:
        cached_at, cached_response = cached
        if (datetime.now(timezone.utc) - cached_at).total_seconds() <= SLEEPING_GIANT_CACHE_SECONDS:
            return cached_response

    with SessionLocal() as db:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No market snapshots are available yet.")
        latest_entries = _latest_market_entries(db, latest_time)
        ranked_symbols = [
            entry.symbol
            for entry in sorted(latest_entries, key=lambda entry: entry.quote_volume_24h, reverse=True)[:max_symbols]
        ]
        latest_snapshot_prices = {entry.symbol: entry.price for entry in latest_entries}
        snapshot_lookback_hours = max(lookback_days * 24, (required_candles + 12) * candle_hours)
        since = latest_time - timedelta(hours=snapshot_lookback_hours)
        snapshot_history = db.scalars(
            select(models.MarketSnapshot)
            .where(models.MarketSnapshot.symbol.in_(ranked_symbols))
            .where(models.MarketSnapshot.timestamp >= since)
            .order_by(models.MarketSnapshot.symbol, models.MarketSnapshot.timestamp)
        ).all()

    binance_client = BinanceFuturesClient(settings)
    try:
        candles_by_symbol = await binance_client.get_klines_for_pionex_symbols(
            ranked_symbols,
            interval=candle_interval,
            limit=candle_limit,
            max_concurrency=8,
        )
    finally:
        await binance_client.close()

    snapshots_by_symbol: dict[str, list[models.MarketSnapshot]] = {symbol: [] for symbol in ranked_symbols}
    for snapshot in snapshot_history:
        snapshots_by_symbol.setdefault(snapshot.symbol, []).append(snapshot)

    for symbol in ranked_symbols:
        if symbol in candles_by_symbol:
            continue
        fallback_candles = _snapshots_to_candles(snapshots_by_symbol.get(symbol, []), hours=candle_hours)
        if fallback_candles:
            candles_by_symbol[symbol] = fallback_candles

    scanner_config = SleepingGiantConfig(
        timeframe=timeframe,
        baseline_candles=baseline_candles,
        compression_min_candles=compression_min_candles,
        compression_max_candles=compression_max_candles,
        require_sleep_window=mode == "strict",
        require_two_candle_confirmation=mode == "strict",
    )
    scanner = RecentAwakeningScanner(scanner_config) if mode == "recent" else SleepingGiantScanner(scanner_config)
    raw_candidates = scanner.scan(candles_by_symbol, limit=max(limit * 3, limit))
    candidates = sorted(
        (
            replace(
                setup,
                current_price=latest_snapshot_prices.get(setup.symbol, setup.current_price),
                score=round(setup.score * _price_relevance_multiplier(latest_snapshot_prices.get(setup.symbol), setup.current_price), 2),
            )
            for setup in raw_candidates
        ),
        key=lambda setup: (
            setup.score,
            setup.height_ratio,
            setup.volume_ratio,
            setup.range_expansion_ratio,
            setup.volume_expansion_ratio,
            setup.compression_score,
        ),
        reverse=True,
    )[:limit]

    response = SleepingGiantResponse(
        latest_report_at=latest_time,
        timeframe=timeframe,
        lookback_days=lookback_days,
        baseline_candles=baseline_candles,
        scanned_symbols=len(candles_by_symbol),
        candidates=[
            SleepingGiantSetupRead(
                symbol=setup.symbol,
                direction=setup.direction,
                awakening_phase=setup.awakening_phase,
                average_candle_size=setup.average_candle_size,
                latest_candle_size=setup.latest_candle_size,
                median_candle_height_pct=setup.median_candle_height_pct,
                latest_candle_height_pct=setup.latest_candle_height_pct,
                height_ratio=setup.height_ratio,
                volume_ratio=setup.volume_ratio,
                body_strength=setup.body_strength,
                two_candle_pressure=setup.two_candle_pressure,
                range_burst_score=setup.range_burst_score,
                volume_burst_score=setup.volume_burst_score,
                compression_score=setup.compression_score,
                breakout_score=setup.breakout_score,
                volume_expansion_ratio=setup.volume_expansion_ratio,
                range_expansion_ratio=setup.range_expansion_ratio,
                distance_from_box_breakout=setup.distance_from_box_breakout,
                current_price=setup.current_price,
                timestamp=datetime.fromtimestamp(setup.timestamp / 1000, tz=timezone.utc) if setup.timestamp else None,
                score=setup.score,
                compression_candles=setup.compression_candles,
                box_high=setup.box_high,
                box_low=setup.box_low,
                notes=setup.notes,
            )
            for setup in candidates
        ],
        note=(
            f"Decision-support scanner only. Uses {timeframe} OHLCV structure where available, with stored Pionex-board snapshots anchoring symbol coverage "
            f"and displayed prices. {note_detail} It does not place trades."
        ),
    )
    _SLEEPING_GIANT_CACHE[cache_key] = (datetime.now(timezone.utc), response)
    return response


@router.get("/market/top-active", response_model=list[ScoreEntry])
def top_active(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.activity_score, limit)


@router.get("/market/top-bullish", response_model=list[ScoreEntry])
def top_bullish(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.bullish_score, limit)


@router.get("/market/top-bearish", response_model=list[ScoreEntry])
def top_bearish(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.bearish_score, limit)


@router.get("/market/top-buyers-left", response_model=list[ScoreEntry])
def top_buyers_left(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.buyer_absence_score, limit)


@router.get("/market/top-dead-markets", response_model=list[ScoreEntry])
def top_dead_markets(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.dead_market_score, limit)


@router.get("/market/top-quiet-rallies", response_model=list[ScoreEntry])
def top_quiet_rallies(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        return _load_scores(db, latest_time, models.CoinScore.quiet_rally_score, limit)


@router.get("/market/watchlist", response_model=list[ScoreEntry])
def watchlist(limit: int = Query(default=20, ge=1, le=100)) -> list[ScoreEntry]:
    with SessionLocal() as db:
        latest_time = _latest_report_time(db)
        if latest_time is None:
            raise HTTPException(status_code=404, detail="No scan results are available yet.")
        snapshots = {
            snapshot.symbol: snapshot
            for snapshot in db.scalars(
                select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_time)
            ).all()
        }
        scores = db.scalars(
            select(models.CoinScore)
            .where(models.CoinScore.report_time == latest_time)
            .where(models.CoinScore.trend_label.like("%Watchlist%"))
            .order_by(
                desc(models.CoinScore.quiet_rally_score),
                desc(models.CoinScore.activity_score),
                desc(models.CoinScore.bullish_score),
            )
            .limit(limit)
        ).all()
        return [models_to_score_entry(score, snapshots.get(score.symbol)) for score in scores]
