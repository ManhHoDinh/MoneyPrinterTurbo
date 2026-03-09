"""
Controller for global application configuration.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import config

router = APIRouter(
    prefix="/api/v1/config",
    tags=["Config"],
)

class YoutubeConfigUpdate(BaseModel):
    client_id: str
    client_secret: str


class RevenueConfigUpdate(BaseModel):
    offer_explore_rate: float
    offer_winner_promote_share: float
    offer_winner_min_impressions: int
    offer_winner_min_lift_ratio: float


@router.get("/youtube")
def get_youtube_config():
    """Get current YouTube OAuth config."""
    return {
        "client_id": config.youtube.get("client_id", ""),
        "client_secret": "****" if config.youtube.get("client_secret") else "",
    }

@router.put("/youtube")
def update_youtube_config(body: YoutubeConfigUpdate):
    """Update YouTube OAuth config in global config.toml."""
    config.youtube["client_id"] = body.client_id
    config.youtube["client_secret"] = body.client_secret
    
    # Save to file
    config.save_config()
    
    return {"status": "success", "message": "YouTube configuration saved"}


@router.get("/revenue")
def get_revenue_config():
    """Get runtime revenue optimization config."""
    return {
        "offer_explore_rate": float(config.app.get("offer_explore_rate", 0.2) or 0.2),
        "offer_winner_promote_share": float(config.app.get("offer_winner_promote_share", 0.75) or 0.75),
        "offer_winner_min_impressions": int(config.app.get("offer_winner_min_impressions", 50) or 50),
        "offer_winner_min_lift_ratio": float(config.app.get("offer_winner_min_lift_ratio", 0.15) or 0.15),
    }


@router.put("/revenue")
def update_revenue_config(body: RevenueConfigUpdate):
    """Update runtime revenue optimization config."""
    explore_rate = max(0.0, min(1.0, float(body.offer_explore_rate)))
    promote_share = max(0.0, min(1.0, float(body.offer_winner_promote_share)))
    min_impressions = max(1, int(body.offer_winner_min_impressions))
    min_lift_ratio = max(0.0, float(body.offer_winner_min_lift_ratio))

    config.app["offer_explore_rate"] = explore_rate
    config.app["offer_winner_promote_share"] = promote_share
    config.app["offer_winner_min_impressions"] = min_impressions
    config.app["offer_winner_min_lift_ratio"] = min_lift_ratio
    config.save_config()

    return {
        "status": "success",
        "message": "Revenue runtime configuration saved",
        "config": {
            "offer_explore_rate": explore_rate,
            "offer_winner_promote_share": promote_share,
            "offer_winner_min_impressions": min_impressions,
            "offer_winner_min_lift_ratio": min_lift_ratio,
        },
    }
