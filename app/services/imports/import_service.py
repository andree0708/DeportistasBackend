"""Orquestador principal de importación de archivos deportivos."""
from __future__ import annotations
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity import ImportedFile, Activity, ActivityMetric, HeartRateSample, PaceSample, ImportStatus, FileFormat
from app.models.runner import RunnerProfile
from app.services.imports.base import ParsedActivity
from app.services.imports.gpx_parser import GPXParser
from app.services.imports.tcx_parser import TCXParser
from app.services.imports.csv_parser import CSVParser
from app.services.imports.fit_parser import FITParser

PARSERS = [FITParser(), GPXParser(), TCXParser(), CSVParser()]

EXTENSION_TO_FORMAT = {
    ".fit": FileFormat.FIT,
    ".gpx": FileFormat.GPX,
    ".tcx": FileFormat.TCX,
    ".csv": FileFormat.CSV,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _save_file(data: bytes, runner_id: str, filename: str) -> str:
    """Guarda el archivo original en disco de forma segura."""
    upload_dir = Path(settings.UPLOAD_DIR) / str(runner_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{Path(filename).name}"
    dest = upload_dir / safe_name
    dest.write_bytes(data)
    return str(dest)


def _detect_format(filename: str) -> FileFormat:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSION_TO_FORMAT:
        raise ValueError(f"Formato no soportado: {ext}. Use .fit, .gpx, .tcx o .csv")
    return EXTENSION_TO_FORMAT[ext]


def process_import(
    db: Session,
    runner_profile: RunnerProfile,
    file_bytes: bytes,
    filename: str,
) -> Tuple[ImportedFile, List[Activity]]:
    """
    Procesa un archivo deportivo completo:
    1. Valida extensión y tamaño.
    2. Detecta duplicados por hash SHA-256.
    3. Parsea el archivo.
    4. Normaliza y persiste actividades.
    5. Registra el archivo importado.
    """
    # Validación de tamaño
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(f"El archivo supera el límite de {settings.MAX_FILE_SIZE_MB} MB")

    file_format = _detect_format(filename)
    file_hash = _sha256(file_bytes)

    # Detección de duplicados por hash
    existing = (
        db.query(ImportedFile)
        .filter(
            ImportedFile.runner_profile_id == runner_profile.id,
            ImportedFile.file_hash_sha256 == file_hash,
            ImportedFile.import_status == ImportStatus.SUCCESS,
        )
        .first()
    )
    if existing:
        import_record = ImportedFile(
            runner_profile_id=runner_profile.id,
            original_filename=filename,
            file_format=file_format,
            file_size_bytes=len(file_bytes),
            file_hash_sha256=file_hash,
            import_status=ImportStatus.DUPLICATE,
            error_message="Archivo idéntico ya importado anteriormente.",
        )
        db.add(import_record)
        db.commit()
        db.refresh(import_record)
        return import_record, []

    # Guardar archivo original
    storage_path = _save_file(file_bytes, str(runner_profile.id), filename)

    import_record = ImportedFile(
        runner_profile_id=runner_profile.id,
        original_filename=filename,
        file_format=file_format,
        file_size_bytes=len(file_bytes),
        file_hash_sha256=file_hash,
        storage_path=storage_path,
        import_status=ImportStatus.PROCESSING,
    )
    db.add(import_record)
    db.flush()

    try:
        # Seleccionar parser
        parser = next((p for p in PARSERS if p.can_parse(filename)), None)
        if not parser:
            raise ValueError(f"No hay parser disponible para {filename}")

        parsed_activities = parser.parse(file_bytes, filename)
        if not parsed_activities:
            raise ValueError("El archivo no contiene actividades válidas")

        created_activities: List[Activity] = []

        for pa in parsed_activities:
            activity = _persist_activity(db, runner_profile.id, import_record.id, pa)
            created_activities.append(activity)

        import_record.import_status = ImportStatus.SUCCESS
        import_record.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(import_record)
        return import_record, created_activities

    except Exception as exc:
        import_record.import_status = ImportStatus.FAILED
        import_record.error_message = str(exc)[:1000]
        db.commit()
        raise


def _persist_activity(
    db: Session,
    runner_profile_id: uuid.UUID,
    imported_file_id: uuid.UUID,
    pa: ParsedActivity,
) -> Activity:
    """Crea una Activity y sus entidades asociadas en la BD."""
    from app.models.activity import ActivityType, MetricSource

    act_type_map = {
        "run": ActivityType.RUN,
        "trail_run": ActivityType.TRAIL_RUN,
        "treadmill": ActivityType.TREADMILL,
        "race": ActivityType.RACE,
        "interval": ActivityType.INTERVAL,
        "recovery_run": ActivityType.RECOVERY_RUN,
    }
    act_type = act_type_map.get(pa.activity_type, ActivityType.OTHER)

    activity = Activity(
        runner_profile_id=runner_profile_id,
        imported_file_id=imported_file_id,
        activity_type=act_type,
        started_at=pa.started_at,
        ended_at=pa.ended_at,
        timezone_name=pa.timezone_name,
        title=pa.title,
        is_demo=False,
    )
    db.add(activity)
    db.flush()

    src_map = {
        "device": MetricSource.DEVICE,
        "user_input": MetricSource.USER_INPUT,
        "estimated": MetricSource.ESTIMATED,
    }

    metric = ActivityMetric(
        activity_id=activity.id,
        distance_meters=pa.distance_meters,
        duration_seconds=pa.duration_seconds,
        avg_pace_sec_per_km=pa.avg_pace_sec_per_km,
        avg_speed_kmh=pa.avg_speed_kmh,
        avg_heart_rate_bpm=pa.avg_heart_rate_bpm,
        max_heart_rate_bpm=pa.max_heart_rate_bpm,
        avg_cadence_spm=pa.avg_cadence_spm,
        elevation_gain_meters=pa.elevation_gain_meters,
        elevation_loss_meters=pa.elevation_loss_meters,
        avg_altitude_meters=pa.avg_altitude_meters,
        training_load=pa.training_load,
        distance_source=src_map.get(pa.distance_source, MetricSource.DEVICE),
        heart_rate_source=src_map.get(pa.heart_rate_source, MetricSource.DEVICE),
        cadence_source=src_map.get(pa.cadence_source, MetricSource.DEVICE),
        raw_data=pa.raw_data or {},
    )
    db.add(metric)

    # Muestras de FC
    for s in pa.heart_rate_samples:
        db.add(HeartRateSample(
            activity_id=activity.id,
            elapsed_seconds=s["elapsed_seconds"],
            heart_rate_bpm=s["heart_rate_bpm"],
        ))

    # Muestras de ritmo
    for s in pa.pace_samples:
        db.add(PaceSample(
            activity_id=activity.id,
            elapsed_seconds=s["elapsed_seconds"],
            pace_sec_per_km=s.get("pace_sec_per_km"),
            distance_meters=s.get("distance_meters"),
        ))

    db.flush()
    return activity
