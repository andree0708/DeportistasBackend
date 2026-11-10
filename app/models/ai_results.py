"""Modelos de resultados de IA: predicciones, estimaciones, anomalías, recomendaciones."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Integer, Float, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    INSUFFICIENT_DATA = "insufficient_data"


class PerformancePrediction(Base):
    __tablename__ = "performance_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True),
                         ForeignKey("activities.id", ondelete="SET NULL"),
                         nullable=True)
    target_distance_km = Column(Float, nullable=False)
    predicted_time_seconds = Column(Float, nullable=True)
    predicted_pace_sec_per_km = Column(Float, nullable=True)
    uncertainty_lower_seconds = Column(Float, nullable=True)
    uncertainty_upper_seconds = Column(Float, nullable=True)
    confidence_level = Column(Float, nullable=True)
    model_version_id = Column(UUID(as_uuid=True),
                              ForeignKey("model_versions.id", ondelete="SET NULL"),
                              nullable=True)
    training_samples_used = Column(Integer, nullable=True)
    is_extrapolation = Column(Boolean, default=False)
    explanatory_factors = Column(JSONB, nullable=True)
    warnings = Column(JSONB, default=list)
    status = Column(SAEnum(PredictionStatus), default=PredictionStatus.PENDING)
    correlation_id = Column(String(100), nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    activity = relationship("Activity", back_populates="predictions")
    model_version = relationship("ModelVersion")


class CapacityEstimate(Base):
    __tablename__ = "capacity_estimates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    best_pace_5k_sec_per_km = Column(Float, nullable=True)
    best_pace_10k_sec_per_km = Column(Float, nullable=True)
    best_pace_half_marathon_sec_per_km = Column(Float, nullable=True)
    aerobic_threshold_pace_sec_per_km = Column(Float, nullable=True)
    estimated_vo2max = Column(Float, nullable=True)
    explanatory_factors = Column(JSONB, nullable=True)
    warnings = Column(JSONB, default=list)
    model_version_id = Column(UUID(as_uuid=True),
                              ForeignKey("model_versions.id", ondelete="SET NULL"),
                              nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AnomalyDetection(Base):
    __tablename__ = "anomaly_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True),
                         ForeignKey("activities.id", ondelete="SET NULL"),
                         nullable=True)
    anomaly_type = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    method_used = Column(String(100), nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    model_version_id = Column(UUID(as_uuid=True),
                              ForeignKey("model_versions.id", ondelete="SET NULL"),
                              nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    recommendation_type = Column(String(100), nullable=False)
    priority = Column(String(20), default="medium")
    title = Column(String(300), nullable=False)
    explanation = Column(Text, nullable=False)
    supporting_data = Column(JSONB, default=list)
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    model_version_id = Column(UUID(as_uuid=True),
                              ForeignKey("model_versions.id", ondelete="SET NULL"),
                              nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    algorithm = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)
    is_global = Column(Boolean, default=True)   # False = personalizado por corredor
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="SET NULL"),
                               nullable=True)
    file_path = Column(String(1000), nullable=True)
    training_samples = Column(Integer, nullable=True)
    feature_names = Column(JSONB, default=list)
    hyperparameters = Column(JSONB, default=dict)
    trained_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(UUID(as_uuid=True),
                              ForeignKey("model_versions.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    r2 = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    extra_metrics = Column(JSONB, default=dict)
    evaluation_set_size = Column(Integer, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    name = Column(String(200), nullable=True)
    scenario_config = Column(JSONB, nullable=False)   # parámetros del escenario
    result = Column(JSONB, nullable=True)             # salida del modelo
    warnings = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
