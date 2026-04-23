"""Routers registered by the main API entrypoint."""

from .admin_queries import router as admin_queries_router
from .market_orders import router as market_orders_router

__all__ = ["admin_queries_router", "market_orders_router"]
