"""Importa todos los modelos para que Alembic los detecte."""
from app.models.user import User, Role, Permission, UserRole
from app.models.runner import RunnerProfile, Device, DataSource, ConsentRecord
from app.models.activity import (
    ImportedFile,
    Activity,
    ActivityMetric,
    HeartRateSample,
    PaceSample,
)
from app.models.recovery import SleepRecord, RecoveryMetric, TrainingLoad
from app.models.training import TrainingGoal
from app.models.ai_results import (
    PerformancePrediction,
    CapacityEstimate,
    AnomalyDetection,
    Recommendation,
    ModelVersion,
    ModelEvaluation,
    SimulationScenario,
)
from app.models.audit import AuditLog

__all__ = [
    "User", "Role", "Permission", "UserRole",
    "RunnerProfile", "Device", "DataSource", "ConsentRecord",
    "ImportedFile", "Activity", "ActivityMetric", "HeartRateSample", "PaceSample",
    "SleepRecord", "RecoveryMetric", "TrainingLoad",
    "TrainingGoal",
    "PerformancePrediction", "CapacityEstimate", "AnomalyDetection",
    "Recommendation", "ModelVersion", "ModelEvaluation", "SimulationScenario",
    "AuditLog",
]
