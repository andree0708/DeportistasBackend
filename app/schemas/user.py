"""Schemas de usuario y perfil del corredor."""
from __future__ import annotations
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RunnerProfileCreate(BaseModel):
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    experience_level: Optional[str] = None
    experience_years: int = 0
    primary_goal: Optional[str] = None
    typical_distances: List[str] = []
    training_days_per_week: Optional[int] = None
    bio: Optional[str] = None


class RunnerProfileUpdate(RunnerProfileCreate):
    pass


class RunnerProfileResponse(RunnerProfileCreate):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceCreate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    device_type: Optional[str] = None
    serial_number: Optional[str] = None


class DeviceResponse(DeviceCreate):
    id: UUID
    is_active: bool
    added_at: datetime

    model_config = {"from_attributes": True}
