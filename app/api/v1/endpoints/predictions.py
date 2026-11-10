"""Endpoints de predicción de rendimiento y estimación de capacidad."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile
from app.models.activity import Activity, ActivityMetric
from app.models.ai_results import PerformancePrediction, PredictionStatus, SimulationScenario
from app.schemas.prediction import (
    PredictionRequestSchema, PredictionResponseSchema,
    SimulationScenarioRequest, SimulationScenarioResponse,
)
from app.grpc_client.ai_client import ai_client

router = APIRouter(prefix="/predictions", tags=["Predicciones y IA"])


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
        if m and m.distance_meters and m.duration_seconds:
            result.append({
                "id": str(act.id),
                "started_at": act.started_at,
                "activity_type": act.activity_type.value,
                "distance_meters": m.distance_meters,
                "duration_seconds": m.duration_seconds,
                "avg_pace_sec_per_km": m.avg_pace_sec_per_km,
                "avg_speed_kmh": m.avg_speed_kmh,
                "avg_heart_rate_bpm": m.avg_heart_rate_bpm,
                "max_heart_rate_bpm": m.max_heart_rate_bpm,
                "avg_cadence_spm": m.avg_cadence_spm,
                "training_load": m.training_load,
            })
    return result


@router.post("/performance", status_code=201)
def predict_performance(
    payload: PredictionRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Solicita predicción de rendimiento al servicio de IA mediante gRPC."""
    profile = _get_profile(current_user, db)
    activities_data = _get_activities_data(profile, db)

    if len(activities_data) < 3:
        raise HTTPException(422, "Se necesitan al menos 3 actividades importadas para generar predicciones")

    profile_dict = {
        "age": profile.age,
        "weight_kg": profile.weight_kg,
        "experience_years": profile.experience_years,
        "primary_goal": profile.primary_goal,
    }

    # Llamada gRPC real
    grpc_result = ai_client.predict_performance(
        runner_id=str(profile.id),
        activities_data=activities_data,
        target_distance_km=payload.target_distance_km,
        profile=profile_dict,
    )

    # Persistir resultado
    pred = PerformancePrediction(
        runner_profile_id=profile.id,
        target_distance_km=payload.target_distance_km,
        predicted_time_seconds=grpc_result.get("predicted_time_seconds"),
        predicted_pace_sec_per_km=grpc_result.get("predicted_pace_sec_per_km"),
        uncertainty_lower_seconds=grpc_result.get("uncertainty", {}).get("lower_bound_seconds") if grpc_result.get("uncertainty") else None,
        uncertainty_upper_seconds=grpc_result.get("uncertainty", {}).get("upper_bound_seconds") if grpc_result.get("uncertainty") else None,
        confidence_level=grpc_result.get("uncertainty", {}).get("confidence_level") if grpc_result.get("uncertainty") else None,
        model_version=None,
        training_samples_used=grpc_result.get("training_samples_used"),
        is_extrapolation=grpc_result.get("is_extrapolation", False),
        explanatory_factors=grpc_result.get("top_factors", []),
        warnings=grpc_result.get("warnings", []),
        status=PredictionStatus.COMPLETED if grpc_result.get("success") else PredictionStatus.FAILED,
        correlation_id=grpc_result.get("correlation_id"),
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    return {
        "id": str(pred.id),
        "target_distance_km": pred.target_distance_km,
        "predicted_time_seconds": pred.predicted_time_seconds,
        "predicted_pace_sec_per_km": pred.predicted_pace_sec_per_km,
        "uncertainty": {
            "lower_bound_seconds": pred.uncertainty_lower_seconds,
            "upper_bound_seconds": pred.uncertainty_upper_seconds,
            "confidence_level": pred.confidence_level,
        } if pred.uncertainty_lower_seconds else None,
        "is_extrapolation": pred.is_extrapolation,
        "top_factors": pred.explanatory_factors,
        "warnings": pred.warnings,
        "status": pred.status.value,
        "generated_at": pred.generated_at.isoformat(),
    }


@router.get("/history", response_model=list)
def prediction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    preds = (
        db.query(PerformancePrediction)
        .filter(PerformancePrediction.runner_profile_id == profile.id)
        .order_by(PerformancePrediction.generated_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "target_distance_km": p.target_distance_km,
            "predicted_time_seconds": p.predicted_time_seconds,
            "predicted_pace_sec_per_km": p.predicted_pace_sec_per_km,
            "is_extrapolation": p.is_extrapolation,
            "status": p.status.value,
            "warnings": p.warnings,
            "generated_at": p.generated_at.isoformat(),
        }
        for p in preds
    ]


@router.post("/simulate", status_code=201)
def simulate_scenario(
    payload: SimulationScenarioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simula un escenario hipotético de rendimiento."""
    profile = _get_profile(current_user, db)
    activities_data = _get_activities_data(profile, db)

    profile_dict = {
        "age": profile.age,
        "weight_kg": profile.weight_kg,
        "experience_years": profile.experience_years,
        "primary_goal": profile.primary_goal,
    }

    grpc_result = ai_client.predict_performance(
        runner_id=str(profile.id),
        activities_data=activities_data,
        target_distance_km=payload.target_distance_km,
        profile=profile_dict,
    )

    scenario = SimulationScenario(
        runner_profile_id=profile.id,
        name=payload.name,
        scenario_config=payload.model_dump(),
        result=grpc_result,
        warnings=grpc_result.get("warnings", []),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return {
        "id": str(scenario.id),
        "name": scenario.name,
        "scenario_config": scenario.scenario_config,
        "result": scenario.result,
        "warnings": scenario.warnings,
        "created_at": scenario.created_at.isoformat(),
    }


@router.get("/ai/health")
def ai_health():
    """Verifica el estado del servicio de IA."""
    return ai_client.check_health()


@router.get("/ai/model-info")
def model_info(
    model_type: str = "prediction",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    return ai_client.get_model_info(str(profile.id), model_type)
