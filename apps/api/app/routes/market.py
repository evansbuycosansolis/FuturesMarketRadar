from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from ..db import SessionLocal
from .. import models
from ..schemas import ScoreEntry, SymbolListResponse, SymbolRead
from ..services.report_service import models_to_score_entry


router = APIRouter(tags=["market"])


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
