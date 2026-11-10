"""Perfil del corredor, dispositivos y consentimientos."""
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


class ExperienceLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ELITE = "elite"


class RunnerProfile(Base):
    __tablename__ = "runner_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     unique=True, nullable=False, index=True)
    age = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    experience_level = Column(SAEnum(ExperienceLevel), nullable=True)
    experience_years = Column(Integer, default=0)
    primary_goal = Column(String(200), nullable=True)
    typical_distances = Column(JSONB, default=list)   # ["5k", "10k"]
    training_days_per_week = Column(Integer, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="runner_profile")
    devices = relationship("Device", back_populates="runner_profile")
    activities = relationship("Activity", back_populates="runner_profile", lazy="dynamic")
    consent_records = relationship("ConsentRecord", back_populates="runner_profile")


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)   # "smartwatch", "chest_strap", etc.
    serial_number = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    runner_profile = relationship("RunnerProfile", back_populates="devices")


class DataSource(Base):
    """Fuente de integración (Garmin Connect, Strava, importación manual, etc.)."""
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    source_type = Column(String(50), nullable=False)   # "file_import", "garmin", "strava"
    source_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True), nullable=True)
    config = Column(JSONB, default=dict)              # Configuración específica (sin credenciales)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConsentRecord(Base):
    """Registro de consentimiento del usuario para fuentes externas."""
    __tablename__ = "consent_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    source_type = Column(String(50), nullable=False)
    granted = Column(Boolean, default=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)   # IPv4/IPv6
    notes = Column(Text, nullable=True)

    runner_profile = relationship("RunnerProfile", back_populates="consent_records")
