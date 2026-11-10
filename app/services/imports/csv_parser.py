"""Parser de archivos CSV de actividades deportivas."""
from __future__ import annotations
import csv
import io
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.services.imports.base import BaseActivityParser, ParsedActivity

COLUMN_ALIASES: Dict[str, str] = {
    "date": "started_at", "start_time": "started_at", "fecha": "started_at",
    "activity date": "started_at", "inicio": "started_at",
    "distance": "distance_m", "distancia": "distance_m",
    "distance (m)": "distance_m", "distance (km)": "distance_km",
    "distancia (km)": "distance_km",
    "elapsed time": "duration_s", "duration": "duration_s",
    "tiempo": "duration_s", "time": "duration_s", "moving time": "duration_s",
    "avg hr": "avg_hr", "average heart rate": "avg_hr",
    "frecuencia cardiaca media": "avg_hr", "fc media": "avg_hr",
    "max hr": "max_hr", "max heart rate": "max_hr",
    "avg pace": "avg_pace", "pace": "avg_pace", "ritmo": "avg_pace",
    "avg pace (min/km)": "avg_pace_minkm",
    "avg cadence": "avg_cad", "cadencia media": "avg_cad",
    "elevation gain": "elev_gain", "desnivel positivo": "elev_gain",
    "elevation loss": "elev_loss", "desnivel negativo": "elev_loss",
    "name": "title", "activity name": "title", "nombre": "title",
    "type": "act_type", "activity type": "act_type", "tipo": "act_type",
}


def _norm(h: str) -> str:
    return h.strip().lower().replace("_", " ")


def _duration_secs(raw: str) -> Optional[float]:
    raw = raw.strip()
    if not raw:
        return None
    parts = raw.split(":")
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(raw)
    except ValueError:
        return None


def _pace_to_sec_km(raw: str) -> Optional[float]:
    raw = raw.strip()
    if not raw:
        return None
    parts = raw.split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(raw)
    except ValueError:
        return None


def _parse_dt(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class CSVParser(BaseActivityParser):

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".csv")

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedActivity]:
        text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("No se pudo decodificar el archivo CSV")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("El CSV no tiene encabezados válidos")

        col_map: Dict[str, str] = {}
        for col in reader.fieldnames:
            norm = _norm(col)
            if norm in COLUMN_ALIASES:
                col_map[col] = COLUMN_ALIASES[norm]

        activities: List[ParsedActivity] = []

        for row in reader:
            m: Dict[str, Any] = {}
            for col, internal in col_map.items():
                val = row.get(col, "").strip()
                if val:
                    m[internal] = val

            started_at = _parse_dt(m.get("started_at", ""))
            if not started_at:
                continue

            distance_m: Optional[float] = None
            if "distance_m" in m:
                try:
                    distance_m = float(m["distance_m"])
                except ValueError:
                    pass
            elif "distance_km" in m:
                try:
                    distance_m = float(m["distance_km"]) * 1000
                except ValueError:
                    pass

            if not distance_m or distance_m <= 0:
                continue

            duration_s = _duration_secs(m.get("duration_s", ""))

            avg_hr: Optional[float] = None
            if "avg_hr" in m:
                try:
                    avg_hr = float(m["avg_hr"])
                except ValueError:
                    pass

            max_hr: Optional[float] = None
            if "max_hr" in m:
                try:
                    max_hr = float(m["max_hr"])
                except ValueError:
                    pass

            avg_cad: Optional[float] = None
            if "avg_cad" in m:
                try:
                    avg_cad = float(m["avg_cad"])
                except ValueError:
                    pass

            avg_pace: Optional[float] = None
            if "avg_pace" in m:
                avg_pace = _pace_to_sec_km(m["avg_pace"])
            elif "avg_pace_minkm" in m:
                avg_pace = _pace_to_sec_km(m["avg_pace_minkm"])

            gain: Optional[float] = None
            if "elev_gain" in m:
                try:
                    gain = float(m["elev_gain"])
                except ValueError:
                    pass

            loss: Optional[float] = None
            if "elev_loss" in m:
                try:
                    loss = float(m["elev_loss"])
                except ValueError:
                    pass

            act_type = str(m.get("act_type", "run")).lower()
            if "run" not in act_type:
                act_type = "other"
            else:
                act_type = "run"

            parsed = ParsedActivity(
                started_at=started_at,
                duration_seconds=duration_s or 0.0,
                distance_meters=distance_m,
                activity_type=act_type,
                title=m.get("title"),
                avg_pace_sec_per_km=avg_pace,
                avg_heart_rate_bpm=avg_hr,
                max_heart_rate_bpm=max_hr,
                avg_cadence_spm=avg_cad,
                elevation_gain_meters=gain,
                elevation_loss_meters=loss,
                distance_source="user_input",
                heart_rate_source="device" if avg_hr else "user_input",
            )
            parsed.compute_derived()
            activities.append(parsed)

        return activities
