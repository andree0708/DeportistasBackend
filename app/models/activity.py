"""Modelos de actividades deportivas e importación."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Integer, Float, Text, Enum as SAEnum, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class FileFormat(str, enum.Enum):
    FIT = "fit"
    GPX = "gpx"
    TCX = "tcx"
    CSV = "csv"


class ActivityType(str, enum.Enum):
    RUN = "run"
    TRAIL_RUN = "trail_run"
    TREADMILL = "treadmill"
    RACE = "race"
    INTERVAL = "interval"
    RECOVERY_RUN = "recovery_run"
    OTHER = "other"


class MetricSource(str, enum.Enum):
    DEVICE = "device"
    USER_INPUT = "user_input"
    ESTIMATED = "estimated"
    SYNTHETIC = "synthetic"


class ImportedFile(Base):
    __tablename__ = "imported_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    file_format = Column(SAEnum(FileFormat), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    file_hash_sha256 = Column(String(64), nullable=True, index=True)  # para detectar duplicados
    storage_path = Column(String(1000), nullable=True)              # ruta interna, no pública
    import_status = Column(SAEnum(ImportStatus), default=ImportStatus.PENDING)
    error_message = Column(Text, nullable=True)
    imported_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)

    activities = relationship("Activity", back_populates="imported_file")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_runner_started", "runner_profile_id", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    imported_file_id = Column(UUID(as_uuid=True),
                              ForeignKey("imported_files.id", ondelete="SET NULL"),
                              nullable=True)
    activity_type = Column(SAEnum(ActivityType), default=ActivityType.RUN)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    timezone_name = Column(String(50), nullable=True)
    title = Column(String(300), nullable=True)
    notes = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False)        # marca datos de demostración
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    runner_profile = relationship("RunnerProfile", back_populates="activities")
    imported_file = relationship("ImportedFile", back_populates="activities")
    metric = relationship("ActivityMetric", back_populates="activity", uselist=False)
    heart_rate_samples = relationship("HeartRateSample", back_populates="activity",
                                      cascade="all, delete-orphan", lazy="dynamic")
    pace_samples = relationship("PaceSample", back_populates="activity",
                                cascade="all, delete-orphan", lazy="dynamic")
    predictions = relationship("PerformancePrediction", back_populates="activity", lazy="dynamic")


class ActivityMetric(Base):
    """Métricas resumen de una actividad (una por actividad)."""
    __tablename__ = "activity_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True),
                         ForeignKey("activities.id", ondelete="CASCADE"),
                         unique=True, nullable=False, index=True)

    distance_meters = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    avg_pace_sec_per_km = Column(Float, nullable=True)
    avg_speed_kmh = Column(Float, nullable=True)
    avg_heart_rate_bpm = Column(Float, nullable=True)
    max_heart_rate_bpm = Column(Float, nullable=True)
    avg_cadence_spm = Column(Float, nullable=True)
    elevation_gain_meters = Column(Float, nullable=True)
    elevation_loss_meters = Column(Float, nullable=True)
    avg_altitude_meters = Column(Float, nullable=True)
    training_load = Column(Float, nullable=True)
    perceived_effort = Column(Integer, nullable=True)   # RPE 1-10

    # Trazabilidad de cada métrica
    distance_source = Column(SAEnum(MetricSource), default=MetricSource.DEVICE)
    heart_rate_source = Column(SAEnum(MetricSource), default=MetricSource.DEVICE)
    cadence_source = Column(SAEnum(MetricSource), default=MetricSource.DEVICE)

    raw_data = Column(JSONB, nullable=True)   # datos adicionales del dispositivo

    activity = relationship("Activity", back_populates="metric")


class HeartRateSample(Base):
    """Muestras de FC a lo largo del tiempo de una actividad."""
    __tablename__ = "heart_rate_samples"
    __table_args__ = (
        Index("ix_hr_samples_activity_elapsed", "activity_id", "elapsed_seconds"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True),
                         ForeignKey("activities.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    elapsed_seconds = Column(Float, nullable=False)
    heart_rate_bpm = Column(Integer, nullable=False)

    activity = relationship("Activity", back_populates="heart_rate_samples")


class PaceSample(Base):
    """Muestras de ritmo a lo largo del tiempo de una actividad."""
    __tablename__ = "pace_samples"
    __table_args__ = (
        Index("ix_pace_samples_activity_elapsed", "activity_id", "elapsed_seconds"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True),
                         ForeignKey("activities.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    elapsed_seconds = Column(Float, nullable=False)
    pace_sec_per_km = Column(Float, nullable=True)
    distance_meters = Column(Float, nullable=True)

    activity = relationship("Activity", back_populates="pace_samples")
