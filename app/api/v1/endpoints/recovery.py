"""Endpoints de recuperación, sueño y análisis de esfuerzo."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile
from app.models.recovery import SleepRecord, RecoveryMetric
from app.models.activity import Activity, ActivityMetric
from app.grpc_client.ai_client import ai_client

router = APIRouter(prefix="/recovery", tags=["Recuperación"])


def _get_profile(user: User, db: Session) -> RunnerProfile:
    p = db.query(RunnerProfile).filter(RunnerProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    return p


class SleepRecordCreate(BaseModel):
    sleep_date: date
    sleep_hours: Optional[float] = None
    sleep_quality_score: Optional[float] = None
    source: str = "user_input"
    notes: Optional[str] = None


class RecoveryMetricCreate(BaseModel):
    metric_date: date
    resting_heart_rate_bpm: Optional[float] = None
    hrv_ms: Optional[float] = None
    recovery_score: Optional[float] = None
    source: str = "user_input"
    notes: Optional[str] = None


@router.post("/sleep", status_code=201)
def log_sleep(
    payload: SleepRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    record = SleepRecord(runner_profile_id=profile.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "message": "Registro de sueño guardado"}


@router.get("/sleep", response_model=list)
def get_sleep_history(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timedelta, datetime, timezone
    profile = _get_profile(current_user, db)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    records = (
        db.query(SleepRecord)
        .filter(SleepRecord.runner_profile_id == profile.id, SleepRecord.sleep_date >= cutoff)
        .order_by(SleepRecord.sleep_date.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "sleep_date": r.sleep_date.isoformat(),
            "sleep_hours": r.sleep_hours,
            "sleep_quality_score": r.sleep_quality_score,
            "source": r.source,
            "notes": r.notes,
        }
        for r in records
    ]


@router.post("/metrics", status_code=201)
def log_recovery_metric(
    payload: RecoveryMetricCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    record = RecoveryMetric(runner_profile_id=profile.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "message": "Métrica de recuperación guardada"}


@router.get("/metrics", response_model=list)
def get_recovery_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timedelta, datetime, timezone
    profile = _get_profile(current_user, db)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    records = (
        db.query(RecoveryMetric)
        .filter(RecoveryMetric.runner_profile_id == profile.id, RecoveryMetric.metric_date >= cutoff)
        .order_by(RecoveryMetric.metric_date.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "metric_date": r.metric_date.isoformat(),
            "resting_heart_rate_bpm": r.resting_heart_rate_bpm,
            "hrv_ms": r.hrv_ms,
            "recovery_score": r.recovery_score,
            "source": r.source,
        }
        for r in records
    ]


@router.get("/analysis")
def analyze_recovery(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Solicita análisis de recuperación al servicio de IA mediante gRPC."""
    profile = _get_profile(current_user, db)

    activities = (
        db.query(Activity)
        .filter(Activity.runner_profile_id == profile.id)
        .order_by(Activity.started_at.desc())
        .limit(50)
        .all()
    )
    activities_data = []
    for act in activities:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        if m:
            activities_data.append({
                "id": str(act.id),
                "started_at": act.started_at,
                "distance_meters": m.distance_meters,
                "duration_seconds": m.duration_seconds,
                "avg_pace_sec_per_km": m.avg_pace_sec_per_km,
                "avg_heart_rate_bpm": m.avg_heart_rate_bpm,
                "activity_type": act.activity_type.value,
            })

    from datetime import timedelta, datetime, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date()
    recovery_records = (
        db.query(RecoveryMetric)
        .filter(RecoveryMetric.runner_profile_id == profile.id, RecoveryMetric.metric_date >= cutoff)
        .all()
    )
    recovery_data = [
        {
            "resting_heart_rate_bpm": r.resting_heart_rate_bpm,
            "hrv_ms": r.hrv_ms,
            "recovery_score": r.recovery_score,
        }
        for r in recovery_records
    ]

    return ai_client.analyze_recovery(
        runner_id=str(profile.id),
        activities_data=activities_data,
        recovery_data=recovery_data,
    )
