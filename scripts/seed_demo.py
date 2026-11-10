"""Puebla la BD con datos realistas para el usuario demo (demo@runsense.ai).

Uso (dentro del contenedor backend):
    python scripts/seed_demo.py [--force] [--skip-ai]

- Fase 1: inserta perfil, dispositivo, 10 semanas de actividades con
  metricas y muestras, sueno, recuperacion, cargas y objetivo.
- Fase 2: llama a la API local (urllib, sin dependencias) para generar
  predicciones, recomendaciones y deteccion de anomalias con la IA real.

Todo el historial va marcado con is_demo=True.
"""
import argparse
import json
import os
import random
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

DEMO_EMAIL = "demo@runsense.ai"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

random.seed(42)
NOW = datetime.now(timezone.utc)
START_DAY = (NOW - timedelta(weeks=10)).date()


# ---------------------------------------------------------------- plan
def build_plan():
    """Genera el plan de sesiones (puro, sin BD): lista de dicts."""
    sessions = []
    easy_base = 385.0  # s/km semana 0 -> mejora progresiva
    for week in range(10):
        monday = START_DAY + timedelta(weeks=week)
        easy = easy_base - week * 1.8
        bad = (week == 6)  # semana de fatiga: ritmos peores y menos sesiones
        plan = [
            ("easy", 1, 7.5 + week * 0.15, easy, "Rodaje suave", 5),
            ("quality", 3, 8.0, easy - (55 if week % 2 == 0 else 70),
             "Tempo" if week % 2 == 0 else "Intervalos 10x400", 7 if week % 2 == 0 else 8),
            ("long", 6, 13.0 + week * 0.55, easy + 8, "Tirada larga", 6),
        ]
        if random.random() < 0.6:
            plan.append(("easy", 5, 5.0, easy + 4, "Rodaje regenerativo", 4))
        if bad:
            plan = [s for s in plan if s[0] != "easy"]  # solo 2 sesiones
        for kind, dow, km, pace, title, rpe in plan:
            if bad:
                pace += pace * 0.08
            pace += random.uniform(-5, 5)
            km = round(km + random.uniform(-0.6, 0.6), 2)
            hr_base = {"easy": 147, "quality": 164, "long": 150}[kind]
            avg_hr = hr_base + random.uniform(-3, 3) + (10 if bad else 0) - week * 0.25
            sessions.append({
                "date": monday + timedelta(days=dow),
                "kind": kind, "distance_km": km,
                "pace": round(pace, 1), "rpe": rpe + (1 if bad else 0),
                "avg_hr": round(avg_hr, 0),
                "max_hr": round(avg_hr + random.uniform(12, 20), 0),
                "cadence": round(random.uniform(170, 182), 0),
                "elev_gain": round(km * random.uniform(8, 15), 0),
                "title": title,
                "hour": 7 if dow in (1, 3) else 8,
            })
    sessions.sort(key=lambda s: s["date"])
    return sessions


# ---------------------------------------------------------------- fase 1
def phase1_db(force=False):
    from app.db.base import SessionLocal
    from app.models.user import User
    from app.models.runner import RunnerProfile, Device, DataSource, ConsentRecord, ExperienceLevel
    from app.models.activity import (
        Activity, ActivityMetric, HeartRateSample, PaceSample,
        ImportedFile, FileFormat, ImportStatus, ActivityType, MetricSource,
    )
    from app.models.recovery import SleepRecord, RecoveryMetric, TrainingLoad
    from app.models.training import TrainingGoal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            raise SystemExit(f"No existe el usuario {DEMO_EMAIL}: crealo con /auth/register primero")
        profile = db.query(RunnerProfile).filter(RunnerProfile.user_id == user.id).first()
        if profile and db.query(Activity).filter(Activity.runner_profile_id == profile.id).count() > 0:
            if not force:
                print("Ya hay actividades demo. Usa --force para regenerar.")
                return None
            print("Limpiando datos demo previos...")
            db.query(Activity).filter(Activity.runner_profile_id == profile.id).delete()
            db.query(ImportedFile).filter(ImportedFile.runner_profile_id == profile.id).delete()
            db.query(SleepRecord).filter(SleepRecord.runner_profile_id == profile.id).delete()
            db.query(RecoveryMetric).filter(RecoveryMetric.runner_profile_id == profile.id).delete()
            db.query(TrainingLoad).filter(TrainingLoad.runner_profile_id == profile.id).delete()
            db.query(TrainingGoal).filter(TrainingGoal.runner_profile_id == profile.id).delete()
            db.query(Device).filter(Device.runner_profile_id == profile.id).delete()
            db.query(DataSource).filter(DataSource.runner_profile_id == profile.id).delete()
            db.commit()

        if not profile:
            profile = RunnerProfile(
                user_id=user.id, age=29, weight_kg=62.0, height_cm=168.0,
                experience_level=ExperienceLevel.INTERMEDIATE, experience_years=3,
                primary_goal="Correr 10K por debajo de 55 minutos",
                typical_distances=["5k", "10k"],
                training_days_per_week=4,
                bio="Corredora aficionada. Entrena antes del trabajo.",
            )
            db.add(profile)
            db.flush()

        db.add(Device(runner_profile_id=profile.id, brand="Garmin",
                      model="Forerunner 265", device_type="smartwatch", is_active=True))
        db.add(DataSource(runner_profile_id=profile.id, source_type="file_import",
                          source_name="Archivos GPX/FIT", is_active=True,
                          notes="Importacion manual desde el reloj"))
        db.add(ConsentRecord(runner_profile_id=profile.id, source_type="file_import",
                             granted=True, granted_at=NOW,
                             notes="Consentimiento para analisis de rendimiento"))
        db.add(TrainingGoal(
            runner_profile_id=profile.id, goal_type="finish_10k",
            target_distance_km=10.0, target_time_seconds=55 * 60,
            target_pace_sec_per_km=330.0,
            target_date=NOW.date() + timedelta(days=60),
            description="Bajar de 55 minutos en 10K", is_active=True))
        db.flush()

        sessions = build_plan()
        formats = [FileFormat.GPX, FileFormat.FIT, FileFormat.FIT, FileFormat.TCX]
        for i, s in enumerate(sessions):
            started = datetime(s["date"].year, s["date"].month, s["date"].day,
                               s["hour"], 0, tzinfo=timezone.utc)
            dist_m = s["distance_km"] * 1000
            dur_s = s["pace"] * s["distance_km"]
            imp = ImportedFile(
                runner_profile_id=profile.id,
                original_filename=f"run_{s['date'].isoformat()}_{s['kind']}.{formats[i % 4].value}",
                file_format=formats[i % 4], file_size_bytes=int(dist_m * 1.7),
                file_hash_sha256=f"{i:064x}"[-64:].replace("0", "a", 6),
                storage_path=f"uploads/{profile.id}/run_{i}",
                import_status=ImportStatus.SUCCESS, imported_at=started,
                processed_at=started + timedelta(seconds=30))
            db.add(imp)
            db.flush()
            act = Activity(
                runner_profile_id=profile.id, imported_file_id=imp.id,
                activity_type=ActivityType.RUN, started_at=started,
                ended_at=started + timedelta(seconds=dur_s),
                timezone_name="Europe/Madrid", title=s["title"], is_demo=True)
            db.add(act)
            db.flush()
            db.add(ActivityMetric(
                activity_id=act.id, distance_meters=round(dist_m, 1),
                duration_seconds=round(dur_s, 1),
                avg_pace_sec_per_km=s["pace"],
                avg_speed_kmh=round(3600.0 / s["pace"], 2),
                avg_heart_rate_bpm=s["avg_hr"], max_heart_rate_bpm=s["max_hr"],
                avg_cadence_spm=s["cadence"],
                elevation_gain_meters=s["elev_gain"],
                elevation_loss_meters=round(s["elev_gain"] * random.uniform(0.85, 1.0), 0),
                training_load=round(s["distance_km"] * (s["avg_hr"] / 150.0), 1),
                perceived_effort=s["rpe"],
                distance_source=MetricSource.DEVICE,
                heart_rate_source=MetricSource.DEVICE,
                cadence_source=MetricSource.DEVICE))
            # muestras de FC cada 30 s con deriva de fatiga
            n = max(4, int(dur_s // 30))
            for k in range(n):
                drift = -8 + 14 * (k / max(n - 1, 1))
                db.add(HeartRateSample(
                    activity_id=act.id, elapsed_seconds=round(k * 30.0, 1),
                    heart_rate_bpm=int(max(95, min(195, s["avg_hr"] + drift + random.uniform(-4, 4))))))
            # parciales por km
            full_km = int(s["distance_km"])
            for km_i in range(1, full_km + 1):
                db.add(PaceSample(
                    activity_id=act.id, elapsed_seconds=round(km_i * s["pace"], 1),
                    pace_sec_per_km=round(s["pace"] + random.uniform(-8, 8), 1),
                    distance_meters=float(km_i * 1000)))

        # sueno y recuperacion diarios
        day = START_DAY
        resting = 54.0
        while day <= NOW.date():
            bad_day = (START_DAY + timedelta(weeks=6)) <= day <= (START_DAY + timedelta(weeks=6, days=6))
            resting += random.uniform(-0.4, 0.3) + (0.5 if bad_day else -0.06)
            resting = max(49.0, min(59.0, resting))
            sleep_h = round(random.uniform(6.4, 8.4) - (1.2 if bad_day and random.random() < 0.4 else 0), 1)
            db.add(SleepRecord(
                runner_profile_id=profile.id, sleep_date=day,
                sleep_hours=sleep_h,
                sleep_quality_score=round(random.uniform(58, 92) - (15 if sleep_h < 6.5 else 0), 0),
                source="device"))
            db.add(RecoveryMetric(
                runner_profile_id=profile.id, metric_date=day,
                resting_heart_rate_bpm=round(resting, 1),
                hrv_ms=round(random.uniform(48, 68) - (8 if bad_day else 0), 1),
                recovery_score=round(random.uniform(62, 90) - (12 if bad_day else 0), 0),
                source="device"))
            day += timedelta(days=1)

        # cargas semanales
        for week in range(10):
            monday = START_DAY + timedelta(weeks=week)
            wk = [s for s in sessions if monday <= s["date"] < monday + timedelta(days=7)]
            acute = round(sum(s["distance_km"] for s in wk), 1)
            prev = [sum(s["distance_km"] for s in sessions
                        if monday - timedelta(weeks=w + 1) <= s["date"] < monday - timedelta(weeks=w))
                    for w in range(4)]
            prev = [p for p in prev if p > 0]
            chronic = round(sum(prev) / len(prev), 1) if prev else acute
            acwr = round(acute / chronic, 2) if chronic else 1.0
            monotony = round(random.uniform(1.1, 1.6), 2)
            db.add(TrainingLoad(
                runner_profile_id=profile.id, load_date=monday + timedelta(days=6),
                acute_load_7d=acute, chronic_load_28d=chronic, acwr=acwr,
                monotony=monotony, strain=round(acute * monotony, 1)))

        db.commit()
        n_act = db.query(Activity).filter(Activity.runner_profile_id == profile.id).count()
        print(f"Fase 1 OK: perfil {profile.id}, {n_act} actividades, sueno/recuperacion/cargas y objetivo.")
        return str(profile.id)
    finally:
        db.close()


# ---------------------------------------------------------------- fase 2
def api(method, path, token=None, payload=None):
    req = urllib.request.Request(
        BACKEND_URL + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}


def phase2_ai():
    print("Login demo...")
    st, login = api("POST", "/api/v1/auth/login",
                    payload={"email": DEMO_EMAIL, "password": "Demo1234!"})
    if st != 200 or "access_token" not in login:
        raise SystemExit(f"Login fallo: {st} {login}")
    tok = login["access_token"]
    for km in (5.0, 10.0, 15.0, 21.1):
        st, r = api("POST", "/api/v1/predictions/performance", tok,
                    {"target_distance_km": km})
        print(f"Prediccion {km}K: HTTP {st} "
              f"{r.get('predicted_time_seconds')}s" if st in (200, 201) else f"Prediccion {km}K fallo: {st} {r}")
    st, r = api("POST", "/api/v1/recommendations/generate", tok)
    print(f"Recomendaciones: HTTP {st} "
          f"({len(r.get('recommendations', []))} generadas)" if st in (200, 201) else f"Recomendaciones fallo: {st}")
    st, r = api("POST", "/api/v1/recommendations/anomalies/detect", tok)
    print(f"Anomalias: HTTP {st}" if st in (200, 201) else f"Anomalias fallo: {st} {r}")
    st, r = api("GET", "/api/v1/recovery/analysis", tok)
    print(f"Analisis recuperacion: HTTP {st}" if st == 200 else f"Recuperacion fallo: {st} {r}")
    st, r = api("POST", "/api/v1/predictions/simulate", tok,
                {"name": "Demo: 10K a 5:30", "target_distance_km": 10.0,
                 "target_pace_sec_per_km": 330.0})
    print(f"Simulacion: HTTP {st}" if st in (200, 201) else f"Simulacion fallo: {st} {r}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="borra y regenera datos demo")
    ap.add_argument("--skip-ai", action="store_true", help="omite la fase 2 (IA)")
    args = ap.parse_args()
    if phase1_db(force=args.force) is None and not args.skip_ai:
        print("Datos ya existentes: ejecutando solo fase 2 (IA)...")
    if not args.skip_ai:
        phase2_ai()
    print("Seed completado.")
