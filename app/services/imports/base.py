"""Clase base para todos los importadores de actividades deportivas."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class ParsedActivity:
    """Resultado normalizado de cualquier importador."""
    # Obligatorios
    started_at: datetime
    duration_seconds: float
    distance_meters: float

    # Opcionales (el importador establece lo que el archivo contiene)
    ended_at: Optional[datetime] = None
    timezone_name: Optional[str] = None
    activity_type: str = "run"
    title: Optional[str] = None

    avg_pace_sec_per_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    avg_heart_rate_bpm: Optional[float] = None
    max_heart_rate_bpm: Optional[float] = None
    avg_cadence_spm: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    elevation_loss_meters: Optional[float] = None
    avg_altitude_meters: Optional[float] = None
    training_load: Optional[float] = None

    # Procedencia
    distance_source: str = "device"
    heart_rate_source: str = "device"
    cadence_source: str = "device"

    # Muestras temporales (pueden ser vacías)
    heart_rate_samples: List[dict] = field(default_factory=list)
    pace_samples: List[dict] = field(default_factory=list)

    # Datos extra del dispositivo (sin normalizar)
    raw_data: dict = field(default_factory=dict)

    def compute_derived(self) -> None:
        """Calcula campos derivados si no están presentes."""
        if self.distance_meters and self.duration_seconds:
            if not self.avg_pace_sec_per_km and self.distance_meters > 0:
                km = self.distance_meters / 1000
                self.avg_pace_sec_per_km = self.duration_seconds / km
            if not self.avg_speed_kmh and self.duration_seconds > 0:
                hours = self.duration_seconds / 3600
                self.avg_speed_kmh = (self.distance_meters / 1000) / hours


class BaseActivityParser(ABC):
    """Interfaz de los parsers de archivos deportivos."""

    @abstractmethod
    def can_parse(self, filename: str) -> bool:
        """Retorna True si este parser maneja el archivo dado."""
        ...

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedActivity]:
        """Parsea el archivo y retorna lista de actividades (puede ser >1 en CSVs de historial)."""
        ...
