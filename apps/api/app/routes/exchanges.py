from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import ExchangeStatusRead, ExchangeStatusResponse


router = APIRouter(tags=["exchanges"])


def _status_mode(enabled: bool, configured: bool, sync_enabled: bool, trading_enabled: bool) -> str:
    if not enabled:
        return "disabled"
    if not configured:
        return "needs_keys"
    if trading_enabled:
        return "live_enabled"
    if sync_enabled:
        return "read_only"
    return "guardrail"


def _status_message(exchange: str, enabled: bool, configured: bool, sync_enabled: bool, trading_enabled: bool) -> str:
    if not enabled:
        return f"{exchange} is available in the app plan but disabled in backend settings."
    if not configured:
        return f"Add {exchange} API credentials before account sync can run."
    if trading_enabled:
        return f"{exchange} execution is enabled. Orders still pass through the app risk gate."
    if sync_enabled:
        return f"{exchange} is configured for account monitoring; live execution remains disabled."
    return f"{exchange} can be used for planning and risk checks, but private sync is disabled."


@router.get("/exchanges/status", response_model=ExchangeStatusResponse)
def exchange_status(request: Request) -> ExchangeStatusResponse:
    settings = request.app.state.settings
    pionex_trading_enabled = settings.enable_trading and settings.enable_private_api and settings.private_api_configured
    binance_trading_requested = (
        settings.enable_trading
        and settings.enable_binance
        and settings.enable_binance_trading
        and settings.binance_configured
    )
    binance_trading_enabled = False

    exchanges = [
        ExchangeStatusRead(
            exchange="pionex",
            label="Pionex Futures",
            enabled=True,
            configured=settings.private_api_configured,
            private_sync_enabled=settings.enable_private_api,
            trading_enabled=pionex_trading_enabled,
            execution_available=pionex_trading_enabled,
            base_url=settings.pionex_base_url,
            mode=_status_mode(True, settings.private_api_configured, settings.enable_private_api, pionex_trading_enabled),
            message=_status_message(
                "Pionex",
                True,
                settings.private_api_configured,
                settings.enable_private_api,
                pionex_trading_enabled,
            ),
        ),
        ExchangeStatusRead(
            exchange="binance",
            label="Binance USD-M Futures",
            enabled=settings.enable_binance,
            configured=settings.binance_configured,
            private_sync_enabled=settings.enable_binance,
            trading_enabled=binance_trading_enabled,
            execution_available=False,
            base_url=settings.binance_base_url,
            mode=_status_mode(
                settings.enable_binance,
                settings.binance_configured,
                settings.enable_binance,
                binance_trading_enabled,
            ),
            message=_status_message(
                "Binance",
                settings.enable_binance,
                settings.binance_configured,
                settings.enable_binance,
                binance_trading_enabled,
            )
            + (
                " Binance live execution was requested in settings, but it remains locked until the Binance execution adapter is implemented."
                if binance_trading_requested
                else " Binance execution adapter is not implemented yet."
            ),
        ),
    ]

    return ExchangeStatusResponse(global_trading_enabled=settings.enable_trading, exchanges=exchanges)
