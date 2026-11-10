"""Parser de archivos FIT (Flexible and Interoperable Data Transfer Protocol).

Requiere la librería fitparse (pip install fitparse).
Si no está disponible, retorna un error explicativo.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List

from app.services.imports.base import BaseActivityParser, ParsedActivity


class FITParser(BaseActivityParser):

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".fit")

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedActivity]:
        try:
            from fitparse import FitFile, FitParseError
        except ImportError:
            raise ValueError(
                "La librería fitparse no está instalada. "
                "Ejecuta: pip install fitparse"
            )

        try:
            fit = FitFile(file_bytes)
        except Exception as exc:
            raise ValueError(f"Archivo FIT inválido: {exc}")

        records = []
        sessions = []
        laps = []

        for msg in fit.get_messages():
            name = msg.name
            if name == "record":
                data = {f.name: f.value for f in msg.fields if f.value is not None}
                records.append(data)
            elif name == "session":
                data = {f.name: f.value for f in msg.fields if f.value is not None}
                sessions.append(data)
            elif name == "lap":
                data = {f.name: f.value for f in msg.fields if f.value is not None}
                laps.append(data)

        if not sessions and not records:
            raise ValueError("El archivo FIT no contiene actividades válidas")

        activities: List[ParsedActivity] = []

        for sess in sessions or [{}]:
            sport = str(sess.get("sport", "running")).lower()
            activity_type = "run" if "run" in sport else "other"

            started_at = sess.get("start_time")
            if isinstance(started_at, datetime) and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            total_distance = sess.get("total_distance") or 0.0
            total_elapsed = sess.get("total_elapsed_time") or sess.get("total_timer_time") or 0.0
            avg_hr = sess.get("avg_heart_rate")
            max_hr = sess.get("max_heart_rate")
            avg_cad = sess.get("avg_running_cadence") or sess.get("avg_cadence")
            if avg_cad:
                avg_cad *= 2  # FIT guarda cadencia por pierna; convertir a pasos/min
            gain = sess.get("total_ascent")
            loss = sess.get("total_descent")

            # Muestras de FC y ritmo desde records
            hr_samples = []
            pace_samples = []
            if started_at:
                for rec in records:
                    ts = rec.get("timestamp")
                    if isinstance(ts, datetime) and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    elapsed = (ts - started_at).total_seconds() if ts and started_at else 0.0

                    if "heart_rate" in rec:
                        hr_samples.append({
                            "elapsed_seconds": elapsed,
                            "heart_rate_bpm": int(rec["heart_rate"]),
                        })

                    dist = rec.get("distance")
                    speed = rec.get("speed")
                    if dist is not None and speed and speed > 0:
                        pace = 1000 / speed  # m/s → s/km
                        pace_samples.append({
                            "elapsed_seconds": elapsed,
                            "pace_sec_per_km": pace,
                            "distance_meters": dist,
                        })

            parsed = ParsedActivity(
                started_at=started_at or datetime.now(timezone.utc),
                duration_seconds=float(total_elapsed),
                distance_meters=float(total_distance),
                activity_type=activity_type,
                avg_heart_rate_bpm=float(avg_hr) if avg_hr is not None else None,
                max_heart_rate_bpm=float(max_hr) if max_hr is not None else None,
                avg_cadence_spm=float(avg_cad) if avg_cad is not None else None,
                elevation_gain_meters=float(gain) if gain is not None else None,
                elevation_loss_meters=float(loss) if loss is not None else None,
                heart_rate_samples=hr_samples[:500],
                pace_samples=pace_samples[:500],
                raw_data={k: str(v) for k, v in sess.items() if k not in (
                    "start_time", "total_distance", "total_elapsed_time",
                    "avg_heart_rate", "max_heart_rate",
                )},
            )
            parsed.compute_derived()
            activities.append(parsed)

        return activities
