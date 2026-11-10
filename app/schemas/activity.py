"""Schemas de actividades y métricas."""
from __future__ import annotations
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ActivityMetricResponse(BaseModel):
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    avg_pace_sec_per_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    avg_heart_rate_bpm: Optional[float] = None
    max_heart_rate_bpm: Optional[float] = None
    avg_cadence_spm: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    elevation_loss_meters: Optional[float] = None
    training_load: Optional[float] = None
    perceived_effort: Optional[int] = None
    distance_source: Optional[str] = None
    heart_rate_source: Optional[str] = None

    model_config = {"from_attributes": True}


class ActivityResponse(BaseModel):
    id: UUID
    activity_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    is_demo: bool
    metric: Optional[ActivityMetricResponse] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    items: List[ActivityResponse]
    total: int
    page: int
    page_size: int


class ImportFileResponse(BaseModel):
    id: UUID
    original_filename: str
    file_format: str
    import_status: str
    error_message: Optional[str] = None
    imported_at: datetime
    activities_count: int = 0

    model_config = {"from_attributes": True}


class ActivityUpdateNotes(BaseModel):
    notes: Optional[str] = None
    perceived_effort: Optional[int] = None
    title: Optional[str] = None
