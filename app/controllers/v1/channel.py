"""
Channel Management Controller — CRUD endpoints for YouTube channels.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.models.channel_schemas import (
    ChannelCreate,
    ChannelUpdate,
    ChannelListOut,
    ChannelOut,
)
from app.services import channel_service

router = APIRouter(
    prefix="/api/v1/channels",
    tags=["Channels"],
)


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(body: ChannelCreate, db: Session = Depends(get_db)):
    """Create a new YouTube channel profile."""
    channel = channel_service.create_channel(db, body)
    return channel_service.channel_to_out(channel)


@router.get("", response_model=ChannelListOut)
def list_channels(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all channels."""
    channels = channel_service.list_channels(db, skip=skip, limit=limit)
    total = channel_service.count_channels(db)
    return ChannelListOut(
        total=total,
        channels=[channel_service.channel_to_out(ch) for ch in channels],
    )


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: str, db: Session = Depends(get_db)):
    """Get channel details by ID."""
    channel = channel_service.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel_service.channel_to_out(channel)


@router.put("/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: str, body: ChannelUpdate, db: Session = Depends(get_db)):
    """Update a channel."""
    channel = channel_service.update_channel(db, channel_id, body)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel_service.channel_to_out(channel)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: str, db: Session = Depends(get_db)):
    """Delete a channel and all associated data."""
    if not channel_service.delete_channel(db, channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    return None
