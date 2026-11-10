"""Modelos de recuperación, sueño y carga de entrenamiento."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Integer, Float, Text, Date, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class SleepRecord(Base):
    __tablename__ = "sleep_records"
    __table_args__ = (
        Index("ix_sleep_runner_date", "runner_profile_id", "sleep_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    sleep_date = Column(Date, nullable=False)
    sleep_hours = Column(Float, nullable=True)
    sleep_quality_score = Column(Float, nullable=True)   # 0-100 si lo provee el dispositivo
    source = Column(String(50), nullable=True)            # "device", "user_input"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RecoveryMetric(Base):
    __tablename__ = "recovery_metrics"
    __table_args__ = (
        Index("ix_recovery_runner_date", "runner_profile_id", "metric_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    metric_date = Column(Date, nullable=False)
    resting_heart_rate_bpm = Column(Float, nullable=True)
    hrv_ms = Column(Float, nullable=True)                # HRV en milisegundos
    recovery_score = Column(Float, nullable=True)        # 0-100 si el dispositivo lo provee
    source = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrainingLoad(Base):
    """Carga de entrenamiento calculada (ACWR, monotonía, etc.)."""
    __tablename__ = "training_loads"
    __table_args__ = (
        Index("ix_training_load_runner_date", "runner_profile_id", "load_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    load_date = Column(Date, nullable=False)
    acute_load_7d = Column(Float, nullable=True)      # Carga aguda 7 días
    chronic_load_28d = Column(Float, nullable=True)   # Carga crónica 28 días
    acwr = Column(Float, nullable=True)               # Acute:Chronic Workload Ratio
    monotony = Column(Float, nullable=True)
    strain = Column(Float, nullable=True)
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
