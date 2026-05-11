from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from nexus_core.observability import get_logger, log_event


logger = get_logger("nexus.rust_sensors")


def _load_sensor_engine():
    try:
        from nexus_sensors import SensorEngineRust

        engine = SensorEngineRust()
        if hasattr(engine, "os_snapshot_json"):
            return engine
    except ImportError:
        pass
    except Exception as exc:
        log_event(logger, 30, "rust_sensors_import_failed", error=str(exc))

    local_extension = (
        Path(__file__).resolve().parents[1]
        / "core-rust"
        / "target"
        / "release"
        / "libnexus_sensors.so"
    )
    if not local_extension.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location("nexus_sensors", local_extension)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = module.SensorEngineRust()
        if hasattr(engine, "os_snapshot_json"):
            return engine
        log_event(logger, 30, "rust_sensors_missing_api", source=str(local_extension))
    except Exception as exc:
        log_event(logger, 30, "rust_sensors_load_failed", error=str(exc))
        return None
    return None


_SENSOR_ENGINE = _load_sensor_engine()
RUST_SENSORS_AVAILABLE = _SENSOR_ENGINE is not None


def get_os_snapshot() -> dict[str, Any] | None:
    if _SENSOR_ENGINE is None:
        return None
    try:
        raw = _SENSOR_ENGINE.os_snapshot_json()
        data = json.loads(raw)
    except Exception as exc:
        log_event(logger, 30, "rust_os_snapshot_failed", error=str(exc))
        return None

    return {
        "cpu_per_core": list(data.get("cpu_per_core") or []),
        "cpu_avg": float(data.get("cpu_avg") or 0.0),
        "ram": float(data.get("ram") or 0.0),
        "disk": float(data.get("disk") or 0.0),
        "top_processes": list(data.get("top_processes") or [])[:3],
        "pressure": str(data.get("pressure") or "calm"),
    }
