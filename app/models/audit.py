"""Registro de auditoría de operaciones del sistema."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True),
                     ForeignKey("users.id", ondelete="SET NULL"),
                     nullable=True, index=True)
    action = Column(String(100), nullable=False)        # "login", "import_activity", etc.
    resource_type = Column(String(100), nullable=True)  # "activity", "prediction", etc.
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    extra_data = Column(JSONB, default=dict)             # datos contextuales SIN PII
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="audit_logs")
