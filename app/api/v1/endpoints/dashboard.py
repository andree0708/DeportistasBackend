"""Endpoint del dashboard principal con métricas agregadas."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile
from app.models.activity import Activity, ActivityMetric
from app.models.ai_results import PerformancePrediction, Recommendation

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(RunnerProfile).filter(RunnerProfile.user_id == current_user.id).first()
    if not profile:
        return {"has_profile": False, "message": "Crea tu perfil para comenzar"}

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # Totales históricos
    total_activities = db.query(func.count(Activity.id)).filter(
        Activity.runner_profile_id == profile.id
    ).scalar() or 0

    # Totales del mes
    month_metrics = (
        db.query(
            func.sum(ActivityMetric.distance_meters).label("dist"),
            func.sum(ActivityMetric.duration_seconds).label("dur"),
            func.avg(ActivityMetric.avg_pace_sec_per_km).label("avg_pace"),
            func.avg(ActivityMetric.avg_heart_rate_bpm).label("avg_hr"),
        )
        .join(Activity, Activity.id == ActivityMetric.activity_id)
        .filter(Activity.runner_profile_id == profile.id, Activity.started_at >= month_start)
        .first()
    )

    # Totales de la semana
    week_metrics = (
        db.query(
            func.sum(ActivityMetric.distance_meters).label("dist"),
            func.count(Activity.id).label("count"),
        )
        .join(Activity, Activity.id == ActivityMetric.activity_id)
        .filter(Activity.runner_profile_id == profile.id, Activity.started_at >= week_start)
        .first()
    )

    # Últimas 5 actividades
    recent_activities = (
        db.query(Activity)
        .filter(Activity.runner_profile_id == profile.id)
        .order_by(Activity.started_at.desc())
        .limit(5)
        .all()
    )

    recent_list = []
    for act in recent_activities:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        recent_list.append({
            "id": str(act.id),
            "title": act.title or act.activity_type.value,
            "started_at": act.started_at.isoformat(),
            "distance_km": round((m.distance_meters or 0) / 1000, 2) if m else None,
            "duration_seconds": m.duration_seconds if m else None,
            "avg_pace_sec_per_km": m.avg_pace_sec_per_km if m else None,
            "avg_heart_rate_bpm": m.avg_heart_rate_bpm if m else None,
            "activity_type": act.activity_type.value,
        })

    # Última predicción
    last_prediction = (
        db.query(PerformancePrediction)
        .filter(PerformancePrediction.runner_profile_id == profile.id)
        .order_by(PerformancePrediction.generated_at.desc())
        .first()
    )

    # Recomendaciones sin leer
    unread_recs = db.query(func.count(Recommendation.id)).filter(
        Recommendation.runner_profile_id == profile.id,
        Recommendation.is_read == False,
        Recommendation.is_dismissed == False,
    ).scalar() or 0

    return {
        "has_profile": True,
        "runner_name": current_user.full_name or current_user.email,
        "total_activities": total_activities,
        "weekly": {
            "distance_km": round((week_metrics.dist or 0) / 1000, 2),
            "activities_count": week_metrics.count or 0,
        },
        "monthly": {
            "distance_km": round((month_metrics.dist or 0) / 1000, 2),
            "duration_hours": round((month_metrics.dur or 0) / 3600, 1),
            "avg_pace_sec_per_km": round(month_metrics.avg_pace or 0, 1),
            "avg_heart_rate_bpm": round(month_metrics.avg_hr or 0, 1) if month_metrics.avg_hr else None,
        },
        "recent_activities": recent_list,
        "last_prediction": {
            "target_distance_km": last_prediction.target_distance_km,
            "predicted_time_seconds": last_prediction.predicted_time_seconds,
            "generated_at": last_prediction.generated_at.isoformat(),
        } if last_prediction else None,
        "unread_recommendations": unread_recs,
    }


@router.get("/evolution")
def performance_evolution(
    days: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evolución del rendimiento en los últimos N días."""
    profile = db.query(RunnerProfile).filter(RunnerProfile.user_id == current_user.id).first()
    if not profile:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    activities = (
        db.query(Activity)
        .filter(Activity.runner_profile_id == profile.id, Activity.started_at >= cutoff)
        .order_by(Activity.started_at.asc())
        .all()
    )

    result = []
    for act in activities:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        if m and m.distance_meters:
            result.append({
                "date": act.started_at.date().isoformat(),
                "distance_km": round((m.distance_meters or 0) / 1000, 2),
                "avg_pace_sec_per_km": m.avg_pace_sec_per_km,
                "avg_heart_rate_bpm": m.avg_heart_rate_bpm,
                "duration_seconds": m.duration_seconds,
            })

    return result
