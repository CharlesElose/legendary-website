# Routes __init__.py
from .auth import router as auth_router
from .gigs import router as gigs_router
from .wallet import router as wallet_router
from .messages import router as messages_router
from .disputes import router as disputes_router
from .notifications import router as notifications_router
from .analytics import router as analytics_router

__all__ = [
    "auth_router",
    "gigs_router",
    "wallet_router",
    "messages_router",
    "disputes_router",
    "notifications_router",
    "analytics_router"
]
