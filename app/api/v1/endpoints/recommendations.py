"""Endpoints de recomendaciones y detección de anomalías."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile
from app.models.activity import Activity, ActivityMetric
from app.models.ai_results import Recommendation, AnomalyDetection
from app.grpc_client.ai_client import ai_client

router = APIRouter(prefix="/recommendations", tags=["Recomendaciones"])


def _get_profile(user: User, db: Session) -> RunnerProfile:
    p = db.query(RunnerProfile).filter(RunnerProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    return p


def _get_activities_data(profile: RunnerProfile, db: Session) -> list:
    activities = (
        db.query(Activity)
        .filter(Activity.runner_profile_id == profile.id)
        .order_by(Activity.started_at.desc())
        .limit(100)
        .all()
    )
    result = []
    for act in activities:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        if m and m.distance_meters:
            result.append({
                "id": str(act.id),
                "started_at": act.started_at,
                "activity_type": act.activity_type.value,
                "distance_meters": m.distance_meters,
                "duration_seconds": m.duration_seconds,
                "avg_pace_sec_per_km": m.avg_pace_sec_per_km,
                "avg_heart_rate_bpm": m.avg_heart_rate_bpm,
                "avg_speed_kmh": m.avg_speed_kmh,
                "avg_cadence_spm": m.avg_cadence_spm,
            })
    return result


@router.post("/generate", status_code=201)
def generate_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Genera recomendaciones personalizadas via gRPC y las persiste."""
    profile = _get_profile(current_user, db)
    activities_data = _get_activities_data(profile, db)

    if len(activities_data) < 3:
        raise HTTPException(422, "Se necesitan al menos 3 actividades para generar recomendaciones")

    result = ai_client.generate_recommendations(
        runner_id=str(profile.id),
        activities_data=activities_data,
        goal=profile.primary_goal or "",
    )

    if result.get("success") and result.get("recommendations"):
        for rec in result["recommendations"]:
            db_rec = Recommendation(
                runner_profile_id=profile.id,
                recommendation_type=str(rec.get("type", "GENERAL")),
                priority=str(rec.get("priority", "medium")).lower(),
                title=rec.get("title", "Recomendación"),
                explanation=rec.get("explanation", ""),
                supporting_data=rec.get("supporting_data_points", []),
            )
            db.add(db_rec)
        db.commit()

    return result


@router.get("", response_model=list)
def list_recommendations(
    only_unread: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    q = db.query(Recommendation).filter(
        Recommendation.runner_profile_id == profile.id,
        Recommendation.is_dismissed == False,
    )
    if only_unread:
        q = q.filter(Recommendation.is_read == False)
    recs = q.order_by(Recommendation.generated_at.desc()).limit(50).all()
    return [
        {
            "id": str(r.id),
            "type": r.recommendation_type,
            "priority": r.priority,
            "title": r.title,
            "explanation": r.explanation,
            "supporting_data": r.supporting_data,
            "is_read": r.is_read,
            "generated_at": r.generated_at.isoformat(),
        }
        for r in recs
    ]


@router.patch("/{rec_id}/read")
def mark_as_read(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.runner_profile_id == profile.id,
    ).first()
    if not rec:
        raise HTTPException(404, "Recomendación no encontrada")
    rec.is_read = True
    db.commit()
    return {"message": "Marcada como leída"}


@router.post("/anomalies/detect", status_code=201)
def detect_anomalies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detecta anomalías en el historial de actividades."""
    profile = _get_profile(current_user, db)
    activities_data = _get_activities_data(profile, db)

    if len(activities_data) < 5:
        raise HTTPException(422, "Se necesitan al menos 5 actividades para detectar anomalías")

    result = ai_client.detect_anomalies(
        runner_id=str(profile.id),
        activities_data=activities_data,
    )

    if result.get("success") and result.get("anomalies"):
        for a in result["anomalies"]:
            db.add(AnomalyDetection(
                runner_profile_id=profile.id,
                activity_id=a.get("activity_id") or None,
                anomaly_type=a.get("anomaly_type", "unknown"),
                score=float(a.get("score", 0)),
                description=a.get("description", ""),
                context=a.get("context", ""),
                method_used=result.get("method_used", ""),
            ))
        db.commit()

    return result


@router.get("/anomalies", response_model=list)
def list_anomalies(
    acknowledged: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    q = db.query(AnomalyDetection).filter(AnomalyDetection.runner_profile_id == profile.id)
    if not acknowledged:
        q = q.filter(AnomalyDetection.is_acknowledged == False)
    anomalies = q.order_by(AnomalyDetection.detected_at.desc()).limit(50).all()
    return [
        {
            "id": str(a.id),
            "anomaly_type": a.anomaly_type,
            "score": a.score,
            "description": a.description,
            "context": a.context,
            "method_used": a.method_used,
            "is_acknowledged": a.is_acknowledged,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in anomalies
    ]
