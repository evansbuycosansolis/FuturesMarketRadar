from __future__ import annotations

from fastapi import APIRouter

from ..schemas import AssetResearchRequest, AssetResearchResponse
from ..services.asset_research_service import AssetResearchService


router = APIRouter(tags=["research"])


@router.post("/research/asset", response_model=AssetResearchResponse)
async def research_asset(payload: AssetResearchRequest) -> AssetResearchResponse:
    service = AssetResearchService()
    return await service.research(payload.query.strip())
