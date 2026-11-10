"""Endpoints de perfil del corredor."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.runner import RunnerProfile, Device
from app.schemas.user import RunnerProfileCreate, RunnerProfileResponse, RunnerProfileUpdate, DeviceCreate, DeviceResponse

router = APIRouter(prefix="/runner", tags=["Perfil del Corredor"])


def _get_profile_or_404(user: User, db: Session) -> RunnerProfile:
    profile = db.query(RunnerProfile).filter(RunnerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado. Créalo primero.")
    return profile


@router.post("/profile", response_model=RunnerProfileResponse, status_code=201)
def create_profile(payload: RunnerProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(RunnerProfile).filter(RunnerProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya tienes un perfil creado")

    profile = RunnerProfile(user_id=current_user.id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profile", response_model=RunnerProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_profile_or_404(current_user, db)


@router.put("/profile", response_model=RunnerProfileResponse)
def update_profile(payload: RunnerProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile_or_404(current_user, db)
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/devices", response_model=DeviceResponse, status_code=201)
def add_device(payload: DeviceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile_or_404(current_user, db)
    device = Device(runner_profile_id=profile.id, **payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile_or_404(current_user, db)
    return db.query(Device).filter(Device.runner_profile_id == profile.id, Device.is_active == True).all()
