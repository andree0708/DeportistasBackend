"""Modelos de objetivos de entrenamiento."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class TrainingGoal(Base):
    __tablename__ = "training_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_profile_id = Column(UUID(as_uuid=True),
                               ForeignKey("runner_profiles.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    goal_type = Column(String(50), nullable=False)        # "finish_5k", "improve_pace", etc.
    target_distance_km = Column(Float, nullable=True)
    target_time_seconds = Column(Float, nullable=True)
    target_pace_sec_per_km = Column(Float, nullable=True)
    target_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    achieved = Column(Boolean, default=False)
    achieved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
