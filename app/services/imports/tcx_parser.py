"""Parser de archivos TCX (Training Center XML de Garmin)."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

from app.services.imports.base import BaseActivityParser, ParsedActivity

TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
ACT_EXT_NS = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"


def _parse_time(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    text = text.strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _t(tag: str) -> str:
    return f"{{{TCX_NS}}}{tag}"


def _ae(tag: str) -> str:
    return f"{{{ACT_EXT_NS}}}{tag}"


class TCXParser(BaseActivityParser):

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".tcx")

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedActivity]:
        root = ET.fromstring(file_bytes.decode("utf-8", errors="replace"))
        activities: List[ParsedActivity] = []

        for activity in root.iter(_t("Activity")):
            sport = activity.attrib.get("Sport", "Running")
            activity_type = "run" if "run" in sport.lower() else "other"

            # ID/fecha de inicio del activity
            id_el = activity.find(_t("Id"))
            started_at = _parse_time(id_el.text if id_el is not None else None)

            laps = list(activity.iter(_t("Lap")))
            if not laps:
                continue

            total_distance = 0.0
            total_time = 0.0
            total_calories = 0
            hr_values = []
            cadence_values = []
            hr_samples = []
            pace_samples = []
            cum_elapsed = 0.0

            for lap in laps:
                dist_el = lap.find(_t("DistanceMeters"))
                time_el = lap.find(_t("TotalTimeSeconds"))
                lap_dist = float(dist_el.text) if dist_el is not None else 0.0
                lap_time = float(time_el.text) if time_el is not None else 0.0
                total_distance += lap_dist
                total_time += lap_time

                for tp in lap.iter(_t("Trackpoint")):
                    time_tp = tp.find(_t("Time"))
                    if time_tp is not None and started_at:
                        ts = _parse_time(time_tp.text)
                        elapsed = (ts - started_at).total_seconds() if ts else cum_elapsed
                    else:
                        elapsed = cum_elapsed

                    hr_el = tp.find(f"{_t('HeartRateBpm')}/{_t('Value')}")
                    if hr_el is not None:
                        try:
                            hr = int(hr_el.text)
                            hr_values.append(hr)
                            hr_samples.append({"elapsed_seconds": elapsed, "heart_rate_bpm": hr})
                        except (ValueError, TypeError):
                            pass

                    # Cadencia desde extensiones
                    for cad_el in tp.iter(_ae("RunCadence")):
                        try:
                            cadence_values.append(int(cad_el.text))
                        except (ValueError, TypeError):
                            pass

                    # Ritmo desde extensiones
                    dist_tp = tp.find(_t("DistanceMeters"))
                    if dist_tp is not None and total_time > 0:
                        try:
                            d = float(dist_tp.text)
                            if d > 0 and elapsed > 0:
                                pace = elapsed / (d / 1000) if d > 0 else None
                                if pace:
                                    pace_samples.append({
                                        "elapsed_seconds": elapsed,
                                        "pace_sec_per_km": pace,
                                        "distance_meters": d,
                                    })
                        except (ValueError, TypeError):
                            pass

                    cum_elapsed += 1

            avg_hr = sum(hr_values) / len(hr_values) if hr_values else None
            max_hr = max(hr_values) if hr_values else None
            avg_cad = sum(cadence_values) / len(cadence_values) if cadence_values else None
            ended_at = None
            if started_at and total_time:
                from datetime import timedelta
                ended_at = started_at + timedelta(seconds=total_time)

            parsed = ParsedActivity(
                started_at=started_at or datetime.now(timezone.utc),
                ended_at=ended_at,
                duration_seconds=total_time,
                distance_meters=total_distance,
                activity_type=activity_type,
                avg_heart_rate_bpm=avg_hr,
                max_heart_rate_bpm=max_hr,
                avg_cadence_spm=avg_cad,
                heart_rate_samples=hr_samples[:500],
                pace_samples=pace_samples[:500],
            )
            parsed.compute_derived()
            activities.append(parsed)

        return activities
