"""Schemas de predicciones y estimaciones de capacidad."""
from __future__ import annotations
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class PredictionRequestSchema(BaseModel):
    target_distance_km: float
    custom_distance_km: Optional[float] = None


class UncertaintyIntervalSchema(BaseModel):
    lower_bound_seconds: float
    upper_bound_seconds: float
    confidence_level: float


class ExplanatoryFactorSchema(BaseModel):
    feature_name: str
    importance: float
    value_used: float
    description: str


class PredictionResponseSchema(BaseModel):
    id: UUID
    target_distance_km: float
    predicted_time_seconds: Optional[float] = None
    predicted_pace_sec_per_km: Optional[float] = None
    uncertainty: Optional[UncertaintyIntervalSchema] = None
    model_version: Optional[str] = None
    model_name: Optional[str] = None
    training_samples_used: Optional[int] = None
    top_factors: List[ExplanatoryFactorSchema] = []
    warnings: List[str] = []
    is_extrapolation: bool = False
    status: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class CapacityEstimateResponse(BaseModel):
    id: UUID
    best_pace_5k_sec_per_km: Optional[float] = None
    best_pace_10k_sec_per_km: Optional[float] = None
    best_pace_half_marathon_sec_per_km: Optional[float] = None
    aerobic_threshold_pace_sec_per_km: Optional[float] = None
    estimated_vo2max: Optional[float] = None
    warnings: List[str] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class SimulationScenarioRequest(BaseModel):
    name: Optional[str] = None
    target_distance_km: float
    target_pace_sec_per_km: Optional[float] = None
    training_frequency_per_week: Optional[int] = None
    custom_params: Optional[dict] = None


class SimulationScenarioResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    scenario_config: dict
    result: Optional[dict] = None
    warnings: List[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}
