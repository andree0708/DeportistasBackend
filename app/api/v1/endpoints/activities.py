"""Endpoints de actividades deportivas."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.config import settings
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile
from app.models.activity import Activity, ActivityMetric, ImportedFile
from app.schemas.activity import ActivityResponse, ActivityListResponse, ImportFileResponse, ActivityUpdateNotes
from app.services.imports.import_service import process_import

router = APIRouter(prefix="/activities", tags=["Actividades"])


def _get_profile(user: User, db: Session) -> RunnerProfile:
    p = db.query(RunnerProfile).filter(RunnerProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Perfil no encontrado. Crea tu perfil antes de importar.")
    return p


@router.post("/import", response_model=ImportFileResponse, status_code=201)
async def import_activity(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Importa un archivo .fit, .gpx, .tcx o .csv."""
    profile = _get_profile(current_user, db)

    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Formato no soportado. Permitidos: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(400, "El archivo está vacío")

    try:
        import_record, activities = process_import(db, profile, contents, file.filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    return ImportFileResponse(
        id=import_record.id,
        original_filename=import_record.original_filename,
        file_format=import_record.file_format.value,
        import_status=import_record.import_status.value,
        error_message=import_record.error_message,
        imported_at=import_record.imported_at,
        activities_count=len(activities),
    )


@router.get("", response_model=ActivityListResponse)
def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    q = db.query(Activity).filter(Activity.runner_profile_id == profile.id)
    if activity_type:
        q = q.filter(Activity.activity_type == activity_type)
    total = q.count()
    items = q.order_by(Activity.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Cargar métricas
    result = []
    for act in items:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        resp = ActivityResponse(
            id=act.id,
            activity_type=act.activity_type.value,
            started_at=act.started_at,
            ended_at=act.ended_at,
            title=act.title,
            notes=act.notes,
            is_demo=act.is_demo,
            metric=m,
            created_at=act.created_at,
        )
        result.append(resp)

    return ActivityListResponse(items=result, total=total, page=page, page_size=page_size)


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(activity_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile(current_user, db)
    act = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.runner_profile_id == profile.id,
    ).first()
    if not act:
        raise HTTPException(404, "Actividad no encontrada")
    m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
    return ActivityResponse(
        id=act.id,
        activity_type=act.activity_type.value,
        started_at=act.started_at,
        ended_at=act.ended_at,
        title=act.title,
        notes=act.notes,
        is_demo=act.is_demo,
        metric=m,
        created_at=act.created_at,
    )


@router.patch("/{activity_id}", response_model=dict)
def update_activity_notes(
    activity_id: str,
    payload: ActivityUpdateNotes,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(current_user, db)
    act = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.runner_profile_id == profile.id,
    ).first()
    if not act:
        raise HTTPException(404, "Actividad no encontrada")
    if payload.notes is not None:
        act.notes = payload.notes
    if payload.title is not None:
        act.title = payload.title
    if payload.perceived_effort is not None:
        m = db.query(ActivityMetric).filter(ActivityMetric.activity_id == act.id).first()
        if m:
            m.perceived_effort = payload.perceived_effort
    db.commit()
    return {"message": "Actividad actualizada"}


@router.get("/{activity_id}/samples", response_model=dict)
def get_activity_samples(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Devuelve muestras de FC y ritmo para gráficas."""
    from app.models.activity import HeartRateSample, PaceSample
    profile = _get_profile(current_user, db)
    act = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.runner_profile_id == profile.id,
    ).first()
    if not act:
        raise HTTPException(404, "Actividad no encontrada")

    hr = db.query(HeartRateSample).filter(HeartRateSample.activity_id == act.id)\
        .order_by(HeartRateSample.elapsed_seconds).limit(500).all()
    pace = db.query(PaceSample).filter(PaceSample.activity_id == act.id)\
        .order_by(PaceSample.elapsed_seconds).limit(500).all()

    return {
        "heart_rate_samples": [{"t": s.elapsed_seconds, "hr": s.heart_rate_bpm} for s in hr],
        "pace_samples": [{"t": s.elapsed_seconds, "pace": s.pace_sec_per_km, "d": s.distance_meters} for s in pace],
    }
