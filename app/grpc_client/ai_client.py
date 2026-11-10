"""Cliente gRPC hacia el servicio de Inteligencia Artificial."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from app.core.config import settings

logger = logging.getLogger(__name__)


def _dt_to_proto(dt: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


def _build_channel() -> grpc.Channel:
    target = f"{settings.AI_SERVICE_HOST}:{settings.AI_SERVICE_PORT}"
    # En producción usar grpc.secure_channel con credenciales TLS
    return grpc.insecure_channel(
        target,
        options=[
            ("grpc.keepalive_time_ms", 10000),
            ("grpc.keepalive_timeout_ms", 5000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.max_receive_message_length", 32 * 1024 * 1024),
        ],
    )


class AIServiceClient:
    """
    Wrapper del cliente gRPC para RunnerAIService.
    Gestiona canal, timeouts y manejo de errores.
    """

    def __init__(self):
        self._channel: Optional[grpc.Channel] = None
        self._stub = None

    def _get_stub(self):
        """Lazy-init del canal y stub gRPC."""
        if self._stub is None:
            try:
                # Importar código generado por protoc
                from app.grpc_client.generated import ai_service_pb2_grpc
                self._channel = _build_channel()
                self._stub = ai_service_pb2_grpc.RunnerAIServiceStub(self._channel)
            except ImportError as e:
                raise RuntimeError(
                    "Código gRPC no generado. Ejecuta scripts/generate_proto.sh"
                ) from e
        return self._stub

    def _correlation_id(self) -> str:
        return str(uuid.uuid4())

    def predict_performance(self, runner_id: str, activities_data: list, target_distance_km: float, profile: dict) -> dict:
        """Solicita predicción de rendimiento al servicio de IA."""
        try:
            from app.grpc_client.generated import (
                ai_service_pb2,
                prediction_pb2,
                activity_pb2,
                common_pb2,
            )
        except ImportError:
            raise RuntimeError("Código gRPC no generado. Ejecuta scripts/generate_proto.sh")

        stub = self._get_stub()
        correlation_id = self._correlation_id()

        # Construir historial de actividades
        activity_metrics = []
        for act in activities_data:
            am = activity_pb2.ActivityMetrics(
                activity_id=str(act.get("id", "")),
                distance_meters=float(act.get("distance_meters") or 0),
                duration_seconds=float(act.get("duration_seconds") or 0),
                avg_pace_sec_per_km=float(act.get("avg_pace_sec_per_km") or 0),
                avg_speed_kmh=float(act.get("avg_speed_kmh") or 0),
                activity_type=act.get("activity_type", "run"),
                data_source=common_pb2.DATA_SOURCE_DEVICE,
            )
            if act.get("avg_heart_rate_bpm"):
                am.avg_heart_rate_bpm = float(act["avg_heart_rate_bpm"])
            if act.get("max_heart_rate_bpm"):
                am.max_heart_rate_bpm = float(act["max_heart_rate_bpm"])
            if act.get("avg_cadence_spm"):
                am.avg_cadence_spm = float(act["avg_cadence_spm"])
            if act.get("started_at"):
                started = act["started_at"]
                if isinstance(started, datetime):
                    am.started_at.CopyFrom(_dt_to_proto(started))
            activity_metrics.append(am)

        history = activity_pb2.ActivityHistory(
            runner_id=runner_id,
            activities=activity_metrics,
            total_count=len(activity_metrics),
        )

        # Distancia objetivo
        distance_map = {
            5.0: common_pb2.RACE_DISTANCE_5K,
            10.0: common_pb2.RACE_DISTANCE_10K,
            15.0: common_pb2.RACE_DISTANCE_15K,
            21.1: common_pb2.RACE_DISTANCE_HALF_MARATHON,
        }
        target_enum = distance_map.get(target_distance_km, common_pb2.RACE_DISTANCE_CUSTOM)

        runner_profile = prediction_pb2.RunnerProfile(
            experience_years=int(profile.get("experience_years") or 0),
            primary_goal=str(profile.get("primary_goal") or ""),
        )
        if profile.get("age"):
            runner_profile.age = int(profile["age"])
        if profile.get("weight_kg"):
            runner_profile.weight_kg = float(profile["weight_kg"])

        request = prediction_pb2.PredictionRequest(
            runner_id=runner_id,
            correlation_id=correlation_id,
            history=history,
            target_distance=target_enum,
            profile=runner_profile,
            requested_at=_dt_to_proto(datetime.now(timezone.utc)),
        )
        if target_enum == common_pb2.RACE_DISTANCE_CUSTOM:
            request.custom_distance_km = target_distance_km

        try:
            response = stub.PredictPerformance(
                request,
                timeout=settings.AI_SERVICE_TIMEOUT_SECONDS,
            )
            return self._prediction_response_to_dict(response)
        except grpc.RpcError as e:
            logger.error("gRPC PredictPerformance error: %s %s", e.code(), e.details())
            return {"success": False, "error": str(e.details()), "code": str(e.code())}

    def check_health(self) -> dict:
        """Verifica el estado del servicio de IA."""
        try:
            from app.grpc_client.generated import ai_service_pb2
        except ImportError:
            return {"status": "UNAVAILABLE", "error": "Código gRPC no generado"}

        stub = self._get_stub()
        try:
            response = stub.CheckHealth(
                ai_service_pb2.HealthCheckRequest(),
                timeout=5,
            )
            return {
                "status": response.status,
                "version": response.version,
                "components": dict(response.component_status),
            }
        except grpc.RpcError as e:
            return {"status": "NOT_SERVING", "error": str(e.details())}

    def get_model_info(self, runner_id: str, model_type: str = "prediction") -> dict:
        """Obtiene información del modelo activo."""
        try:
            from app.grpc_client.generated import ai_service_pb2
        except ImportError:
            return {"error": "Código gRPC no generado"}

        stub = self._get_stub()
        try:
            response = stub.GetModelInformation(
                ai_service_pb2.ModelInfoRequest(
                    runner_id=runner_id,
                    model_type=model_type,
                ),
                timeout=settings.AI_SERVICE_TIMEOUT_SECONDS,
            )
            return {
                "model_name": response.model_name,
                "version": response.model_version,
                "algorithm": response.algorithm,
                "training_samples": response.training_samples,
                "is_personalized": response.is_personalized,
                "evaluation_metrics": dict(response.evaluation_metrics),
            }
        except grpc.RpcError as e:
            logger.error("gRPC GetModelInformation error: %s", e.details())
            return {"error": str(e.details())}

    def analyze_recovery(self, runner_id: str, activities_data: list, recovery_data: list) -> dict:
        """Solicita análisis de recuperación."""
        try:
            from app.grpc_client.generated import (
                recovery_pb2,
                activity_pb2,
            )
        except ImportError:
            raise RuntimeError("Código gRPC no generado")

        stub = self._get_stub()
        correlation_id = self._correlation_id()

        activity_metrics = self._build_activity_metrics_list(activities_data)
        history = activity_pb2.ActivityHistory(
            runner_id=runner_id,
            activities=activity_metrics,
            total_count=len(activity_metrics),
        )

        rec_protos = []
        for rd in recovery_data:
            rm = recovery_pb2.RecoveryMetrics(
                runner_id=runner_id,
            )
            if rd.get("resting_heart_rate_bpm"):
                rm.resting_heart_rate_bpm = float(rd["resting_heart_rate_bpm"])
            if rd.get("hrv_ms"):
                rm.hrv_ms = float(rd["hrv_ms"])
            if rd.get("sleep_hours"):
                rm.sleep_hours = float(rd["sleep_hours"])
            rec_protos.append(rm)

        request = recovery_pb2.RecoveryAnalysisRequest(
            runner_id=runner_id,
            correlation_id=correlation_id,
            history=history,
            recovery_data=rec_protos,
            requested_at=_dt_to_proto(datetime.now(timezone.utc)),
        )
        try:
            response = stub.AnalyzeRecovery(
                request,
                timeout=settings.AI_SERVICE_TIMEOUT_SECONDS,
            )
            return {
                "success": response.success,
                "current_fatigue_index": response.current_fatigue_index if response.HasField("current_fatigue_index") else None,
                "recovery_trend": response.recovery_trend if response.HasField("recovery_trend") else None,
                "signals": [
                    {
                        "signal_type": s.signal_type,
                        "severity": s.severity,
                        "description": s.description,
                        "recommendation": s.recommendation,
                    }
                    for s in response.signals
                ],
                "warnings": list(response.warnings),
            }
        except grpc.RpcError as e:
            logger.error("gRPC AnalyzeRecovery error: %s", e.details())
            return {"success": False, "error": str(e.details())}

    def generate_recommendations(self, runner_id: str, activities_data: list, goal: str) -> dict:
        """Solicita recomendaciones personalizadas."""
        try:
            from app.grpc_client.generated import recommendation_pb2, activity_pb2
        except ImportError:
            raise RuntimeError("Código gRPC no generado")

        stub = self._get_stub()
        correlation_id = self._correlation_id()

        activity_metrics = self._build_activity_metrics_list(activities_data)
        history = activity_pb2.ActivityHistory(
            runner_id=runner_id,
            activities=activity_metrics,
            total_count=len(activity_metrics),
        )
        request = recommendation_pb2.RecommendationRequest(
            runner_id=runner_id,
            correlation_id=correlation_id,
            history=history,
            primary_goal=goal or "",
            requested_at=_dt_to_proto(datetime.now(timezone.utc)),
        )
        try:
            response = stub.GenerateRecommendations(
                request,
                timeout=settings.AI_SERVICE_TIMEOUT_SECONDS,
            )
            return {
                "success": response.success,
                "recommendations": [
                    {
                        "id": r.id,
                        "type": r.type,
                        "priority": r.priority,
                        "title": r.title,
                        "explanation": r.explanation,
                        "supporting_data_points": list(r.supporting_data_points),
                    }
                    for r in response.recommendations
                ],
                "warnings": list(response.warnings),
            }
        except grpc.RpcError as e:
            logger.error("gRPC GenerateRecommendations error: %s", e.details())
            return {"success": False, "error": str(e.details())}

    def detect_anomalies(self, runner_id: str, activities_data: list) -> dict:
        """Solicita detección de anomalías."""
        try:
            from app.grpc_client.generated import ai_service_pb2, activity_pb2
        except ImportError:
            raise RuntimeError("Código gRPC no generado")

        stub = self._get_stub()
        correlation_id = self._correlation_id()

        activity_metrics = self._build_activity_metrics_list(activities_data)
        history = activity_pb2.ActivityHistory(
            runner_id=runner_id,
            activities=activity_metrics,
            total_count=len(activity_metrics),
        )
        request = ai_service_pb2.AnomalyDetectionRequest(
            runner_id=runner_id,
            correlation_id=correlation_id,
            history=history,
            requested_at=_dt_to_proto(datetime.now(timezone.utc)),
        )
        try:
            response = stub.DetectAnomalies(
                request,
                timeout=settings.AI_SERVICE_TIMEOUT_SECONDS,
            )
            return {
                "success": response.success,
                "anomalies": [
                    {
                        "anomaly_type": a.anomaly_type,
                        "score": a.score,
                        "description": a.description,
                        "context": a.context,
                        "activity_id": a.activity_id,
                    }
                    for a in response.anomalies
                ],
                "method_used": response.method_used,
                "warnings": list(response.warnings),
            }
        except grpc.RpcError as e:
            logger.error("gRPC DetectAnomalies error: %s", e.details())
            return {"success": False, "error": str(e.details())}

    # ------------------------------------------------------------------ helpers

    def _build_activity_metrics_list(self, activities_data: list) -> list:
        try:
            from app.grpc_client.generated import activity_pb2, common_pb2
        except ImportError:
            return []
        result = []
        for act in activities_data:
            am = activity_pb2.ActivityMetrics(
                activity_id=str(act.get("id", "")),
                distance_meters=float(act.get("distance_meters") or 0),
                duration_seconds=float(act.get("duration_seconds") or 0),
                avg_pace_sec_per_km=float(act.get("avg_pace_sec_per_km") or 0),
                avg_speed_kmh=float(act.get("avg_speed_kmh") or 0),
                activity_type=act.get("activity_type", "run"),
                data_source=common_pb2.DATA_SOURCE_DEVICE,
            )
            if act.get("avg_heart_rate_bpm"):
                am.avg_heart_rate_bpm = float(act["avg_heart_rate_bpm"])
            if act.get("avg_cadence_spm"):
                am.avg_cadence_spm = float(act["avg_cadence_spm"])
            if act.get("started_at") and isinstance(act["started_at"], datetime):
                am.started_at.CopyFrom(_dt_to_proto(act["started_at"]))
            result.append(am)
        return result

    def _prediction_response_to_dict(self, resp) -> dict:
        result = {
            "success": resp.success,
            "runner_id": resp.runner_id,
            "correlation_id": resp.correlation_id,
            "predicted_time_seconds": None,
            "predicted_pace_sec_per_km": None,
            "uncertainty": None,
            "model_version": resp.model_version,
            "model_name": resp.model_name,
            "training_samples_used": resp.training_samples_used,
            "is_extrapolation": resp.is_extrapolation,
            "top_factors": [],
            "warnings": list(resp.warnings),
            "errors": [{"code": e.code, "message": e.message} for e in resp.errors],
        }
        if resp.HasField("predicted_time_seconds"):
            result["predicted_time_seconds"] = resp.predicted_time_seconds
        if resp.HasField("predicted_pace_sec_per_km"):
            result["predicted_pace_sec_per_km"] = resp.predicted_pace_sec_per_km
        if resp.HasField("uncertainty"):
            result["uncertainty"] = {
                "lower_bound_seconds": resp.uncertainty.lower_bound_seconds,
                "upper_bound_seconds": resp.uncertainty.upper_bound_seconds,
                "confidence_level": resp.uncertainty.confidence_level,
            }
        for f in resp.top_factors:
            result["top_factors"].append({
                "feature_name": f.feature_name,
                "importance": f.importance,
                "value_used": f.value_used,
                "description": f.description,
            })
        return result

    def close(self):
        if self._channel:
            self._channel.close()


# Instancia singleton
ai_client = AIServiceClient()
