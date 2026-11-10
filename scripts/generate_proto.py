"""Genera código Python de cliente gRPC para el Backend."""
import os
import sys
import subprocess
from pathlib import Path

PROTO_DIR = Path(__file__).parent.parent / "proto"
OUT_DIR = Path(__file__).parent.parent / "app" / "grpc_client" / "generated"
OUT_DIR.mkdir(parents=True, exist_ok=True)

(OUT_DIR / "__init__.py").write_text("# Código generado automáticamente desde archivos .proto\n")

PROTO_FILES = [
    "common.proto",
    "activity.proto",
    "prediction.proto",
    "recovery.proto",
    "recommendation.proto",
    "narrative.proto",
    "ai_service.proto",
]

print(f"Generando codigo cliente gRPC desde {PROTO_DIR} -> {OUT_DIR}")

for proto in PROTO_FILES:
    proto_path = PROTO_DIR / proto
    if not proto_path.exists():
        print(f"  [WARN] No encontrado: {proto_path}")
        continue

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        str(proto_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK] {proto}")
    else:
        print(f"  [ERROR] {proto}:\n{result.stderr}")

print("\nCorrigiendo imports...")
for py_file in OUT_DIR.glob("*.py"):
    if py_file.name == "__init__.py":
        continue
    content = py_file.read_text(encoding="utf-8")
    fixed = content
    for proto in PROTO_FILES:
        module_name = proto.replace(".proto", "_pb2")
        fixed = fixed.replace(
            f"import {module_name}",
            f"from app.grpc_client.generated import {module_name}",
        )
    if fixed != content:
        py_file.write_text(fixed)

print("Codigo cliente gRPC generado.")
