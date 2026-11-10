"""Parser de archivos GPX (GPS Exchange Format)."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional
import math

from app.services.imports.base import BaseActivityParser, ParsedActivity


GPX_NS = {
    "gpx": "http://www.topografix.com/GPX/1/1",
    "gpx10": "http://www.topografix.com/GPX/1/0",
    "gpxtpx": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos coordenadas GPS."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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


class GPXParser(BaseActivityParser):

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".gpx")

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedActivity]:
        root = ET.fromstring(file_bytes.decode("utf-8", errors="replace"))

        # Detecta namespace
        ns_prefix = "gpx"
        if root.tag.startswith("{http://www.topografix.com/GPX/1/0}"):
            ns_prefix = "gpx10"

        def find(elem, path):
            return elem.find(path.replace("gpx:", f"{{{GPX_NS[ns_prefix]}}}").replace("gpx:", f"{{{GPX_NS[ns_prefix]}}}"), GPX_NS)

        activities: List[ParsedActivity] = []

        for trk in root.iter(f"{{{GPX_NS[ns_prefix]}}}trk"):
            name_el = trk.find(f"{{{GPX_NS[ns_prefix]}}}name")
            title = name_el.text if name_el is not None else None

            points = []
            for trkpt in trk.iter(f"{{{GPX_NS[ns_prefix]}}}trkpt"):
                try:
                    lat = float(trkpt.attrib["lat"])
                    lon = float(trkpt.attrib["lon"])
                except (KeyError, ValueError):
                    continue

                time_el = trkpt.find(f"{{{GPX_NS[ns_prefix]}}}time")
                ele_el = trkpt.find(f"{{{GPX_NS[ns_prefix]}}}ele")
                ts = _parse_time(time_el.text if time_el is not None else None)
                ele = float(ele_el.text) if ele_el is not None else None

                # Frecuencia cardíaca desde extensiones Garmin
                hr = None
                for ext in trkpt.iter(f"{{{GPX_NS['gpxtpx']}}}hr"):
                    try:
                        hr = int(ext.text)
                    except (ValueError, TypeError):
                        pass

                # Cadencia desde extensiones Garmin
                cad = None
                for ext in trkpt.iter(f"{{{GPX_NS['gpxtpx']}}}cad"):
                    try:
                        cad = int(ext.text)
                    except (ValueError, TypeError):
                        pass

                points.append({"lat": lat, "lon": lon, "time": ts, "ele": ele, "hr": hr, "cad": cad})

            if len(points) < 2:
                continue

            # Calcular distancia total
            total_distance = 0.0
            for i in range(1, len(points)):
                total_distance += _haversine_m(
                    points[i - 1]["lat"], points[i - 1]["lon"],
                    points[i]["lat"], points[i]["lon"],
                )

            times = [p["time"] for p in points if p["time"]]
            started_at = times[0] if times else datetime.now(timezone.utc)
            ended_at = times[-1] if times else None
            duration = (ended_at - started_at).total_seconds() if ended_at and started_at else 0.0

            # Desnivel
            eles = [p["ele"] for p in points if p["ele"] is not None]
            gain = loss = 0.0
            for i in range(1, len(eles)):
                diff = eles[i] - eles[i - 1]
                if diff > 0:
                    gain += diff
                else:
                    loss += abs(diff)

            # FC
            hrs = [p["hr"] for p in points if p["hr"] is not None]
            avg_hr = sum(hrs) / len(hrs) if hrs else None
            max_hr = max(hrs) if hrs else None

            # Cadencia
            cads = [p["cad"] for p in points if p["cad"] is not None]
            avg_cad = sum(cads) / len(cads) if cads else None

            # Muestras de FC y ritmo
            hr_samples = []
            pace_samples = []
            for i, p in enumerate(points):
                if p["time"] and started_at:
                    elapsed = (p["time"] - started_at).total_seconds()
                    if p["hr"] is not None:
                        hr_samples.append({"elapsed_seconds": elapsed, "heart_rate_bpm": p["hr"]})
                    if i > 0 and points[i - 1]["time"]:
                        seg_dist = _haversine_m(
                            points[i - 1]["lat"], points[i - 1]["lon"],
                            p["lat"], p["lon"]
                        )
                        seg_time = (p["time"] - points[i - 1]["time"]).total_seconds()
                        if seg_dist > 0 and seg_time > 0:
                            seg_pace = seg_time / (seg_dist / 1000)
                            pace_samples.append({
                                "elapsed_seconds": elapsed,
                                "pace_sec_per_km": seg_pace,
                                "distance_meters": total_distance,
                            })

            avg_alt = sum(eles) / len(eles) if eles else None

            parsed = ParsedActivity(
                started_at=started_at,
                ended_at=ended_at,
                duration_seconds=max(duration, 0.0),
                distance_meters=total_distance,
                title=title,
                avg_heart_rate_bpm=avg_hr,
                max_heart_rate_bpm=max_hr,
                avg_cadence_spm=avg_cad,
                elevation_gain_meters=gain if gain > 0 else None,
                elevation_loss_meters=loss if loss > 0 else None,
                avg_altitude_meters=avg_alt,
                heart_rate_samples=hr_samples[:500],  # Límite para no sobrecargar BD
                pace_samples=pace_samples[:500],
            )
            parsed.compute_derived()
            activities.append(parsed)

        return activities
