"""
pipeline/normalizer.py
Normalizes all units to a common standard:
  - Vendor A: Clean JSON (soilMoisture %, ISO ts) → native
  - Vendor B: Epoch + fraction (sm as vwc, epoch ts) → convert fraction to %, epoch to ISO
  - Vendor C: Nested + permille (val in permille, space-separated ts) → convert ÷10
  - Vendor D: Compact integers (m as integer %) → integer to float, epoch to ISO
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Unit confidence by conversion type
UNIT_CONFIDENCE = {
    "native":           1.0,
    "known_conversion": 0.8,
    "heuristic":        0.5,
    "unknown":          0.2,
}

REQUIRED_FIELDS = ["temperature", "humidity", "moisture", "ph", "oxygen", "ammonia", "turbidity"]


def _epoch_to_iso(value, unit="s") -> str:
    try:
        v = float(value)
        ts = v / 1000 if unit == "ms" else v
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def normalize_vendor_a(payload: dict) -> dict:
    """
    Vendor A — Clean JSON: {"deviceId": "sm-01", "ts": "...", "soilMoisture": 23.4, "unit": "%", "plot": "P1"}
    Native units, no conversion needed.
    """
    ts = payload.get("ts", payload.get("timestamp", datetime.now(timezone.utc).isoformat()))
    plot_id = payload.get("plot", "P1")
    sensor_id = payload.get("deviceId", payload.get("sensor_id", "unknown"))

    result = {
        "moisture":    float(payload.get("soilMoisture", payload.get("moisture_pct",
                             payload.get("moisture", 35.0)))),
        "temperature": float(payload.get("airTemperature", payload.get("temperature_c",
                             payload.get("temperature", 22.0)))),
        "ph":          float(payload.get("soilPH", payload.get("ph_value",
                             payload.get("ph", 6.8)))),
        "humidity":    float(payload.get("humidity", 55.0)),
        "oxygen":      float(payload.get("oxygen", payload.get("oxygen_mgl", 8.0))),
        "ammonia":     float(payload.get("ammonia", payload.get("ammonia_mgl", 5.0))),
        "turbidity":   float(payload.get("turbidity", payload.get("turbidity_ntu", 30.0))),
        "batteryLevel": float(payload.get("batteryLevel", payload.get("battery", 75.0))),
        "timestamp":   str(ts).replace(" ", "T"),
        "sensor_id":   sensor_id,
        "_vendor":     "A",
        "_plot":       plot_id,
        "_unit_confidence": UNIT_CONFIDENCE["native"],
        "_conversions": [],
    }
    return result


def normalize_vendor_b(payload: dict) -> dict:
    """
    Vendor B — Epoch + fraction: {"id": "node7", "time": 1772273700, "sm": 0.234, "sm_unit": "vwc", "field": "plot-1"}
    sm is volumetric water content (fraction) → multiply by 100 for %
    time is epoch seconds → ISO
    """
    conversions = []

    # Soil moisture: fraction → %
    sm_frac = float(payload.get("sm", payload.get("moi", 0.35)))
    moisture = sm_frac * 100 if sm_frac <= 1.0 else sm_frac  # guard if already %
    conversions.append("soilMoisture: vwc_fraction→%")

    # Timestamp: epoch → ISO
    epoch = payload.get("time", payload.get("ts", 0))
    ts_iso = _epoch_to_iso(epoch, unit="s")
    conversions.append("timestamp: epoch_s→ISO")

    # Plot ID from "field" field
    field_raw = payload.get("field", "plot-1")
    plot_id = str(field_raw).replace("plot-", "P").strip()

    # Temperature
    temp_c = float(payload.get("temp_c", payload.get("temp_f", 22.0)))
    if "temp_f" in payload and "temp_c" not in payload:
        temp_c = (temp_c - 32) * 5 / 9
        conversions.append("temperature: °F→°C")

    result = {
        "moisture":    round(moisture, 2),
        "temperature": round(temp_c, 2),
        "ph":          float(payload.get("ph", 6.8)),
        "humidity":    float(payload.get("humidity", 55.0)),
        "oxygen":      float(payload.get("oxy", payload.get("oxygen", 8.0))),
        "ammonia":     float(payload.get("amm", payload.get("ammonia", 5.0))),
        "turbidity":   float(payload.get("turb", payload.get("turbidity", 30.0))),
        "batteryLevel": float(payload.get("battery", payload.get("batt", 75.0))),
        "timestamp":   ts_iso,
        "sensor_id":   payload.get("id", payload.get("node", "unknown")),
        "_vendor":     "B",
        "_plot":       plot_id,
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


def normalize_vendor_c(payload: dict) -> dict:
    """
    Vendor C — Nested + permille:
    {"meta": {"dev": "A9", "plot": "P1"}, "obs": {"t": "2026-02-28 10:15:00", "val": 234},
     "type": "SOIL_MOIST", "scale": "permille"}
    val in permille → divide by 10 for %
    """
    conversions = []

    meta = payload.get("meta", {})
    obs_data = payload.get("obs", {})
    scale = payload.get("scale", "percent")

    # Sensor and plot
    sensor_id = meta.get("dev", meta.get("device", "unknown"))
    plot_id = meta.get("plot", "P1")

    # Timestamp from obs.t
    ts_raw = obs_data.get("t", meta.get("timestamp", datetime.now(timezone.utc).isoformat()))
    ts_str = str(ts_raw).replace(" ", "T").strip()
    if "+" not in ts_str and "Z" not in ts_str and len(ts_str) >= 16:
        ts_str += "+00:00"
    conversions.append("timestamp: space-separated→ISO")

    # Value + scale
    val_raw = obs_data.get("val", obs_data.get("value"))
    obs_type = payload.get("type", "SOIL_MOIST")

    moisture = 35.0
    if val_raw is not None:
        val = float(val_raw)
        if scale == "permille":
            moisture = val / 10.0
            conversions.append("soilMoisture: permille→%")
        elif scale == "fraction":
            moisture = val * 100.0
            conversions.append("soilMoisture: fraction→%")
        else:
            moisture = val

    # Nested legacy structure
    env = payload.get("data", {}).get("env", {})
    soil = payload.get("data", {}).get("soil", {})
    water = payload.get("data", {}).get("water", {})

    hum_pm = env.get("humidity_pm")
    humidity = float(hum_pm) / 10.0 if hum_pm is not None else float(payload.get("humidity", 55.0))

    moi_pm = soil.get("moisture_pm")
    if moi_pm is not None and moisture == 35.0:
        moisture = float(moi_pm) / 10.0
        conversions.append("moisture: permille→%")

    result = {
        "moisture":    round(moisture, 2),
        "temperature": float(env.get("temperature_c", payload.get("airTemperature",
                             payload.get("temperature", 22.0)))),
        "ph":          float(soil.get("ph", payload.get("soilPH", payload.get("ph", 6.8)))),
        "humidity":    round(humidity, 2),
        "oxygen":      float(water.get("oxygen_mgl", payload.get("oxygen", 8.0))),
        "ammonia":     float(water.get("ammonia_mgl", payload.get("ammonia", 5.0))),
        "turbidity":   float(water.get("turbidity_ntu", payload.get("turbidity", 30.0))),
        "batteryLevel": float(payload.get("batteryLevel", payload.get("battery", 75.0))),
        "timestamp":   ts_str,
        "sensor_id":   sensor_id,
        "_vendor":     "C",
        "_plot":       plot_id,
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


def normalize_vendor_d(payload: dict) -> dict:
    """
    Vendor D — Compact: {"d": "19", "t": 1772273700, "m": 23, "k": "SM"}
    m is integer % soil moisture, t is epoch seconds
    """
    conversions = []

    # Timestamp: epoch → ISO
    epoch = payload.get("t", payload.get("ts", 0))
    ts_iso = _epoch_to_iso(epoch, unit="s")
    conversions.append("timestamp: epoch_s→ISO")

    # Values from compact keys
    moisture = float(payload.get("m", payload.get("moisture", 35)))
    temp = float(payload.get("temp", payload.get("t_val", 22)))
    # ph is encoded as ph_x10 / 10
    ph_x10 = payload.get("ph_x10")
    ph = float(ph_x10) / 10.0 if ph_x10 is not None else float(payload.get("ph", 6.8))

    result = {
        "moisture":    float(moisture),
        "temperature": float(temp),
        "ph":          float(ph),
        "humidity":    float(payload.get("h", payload.get("humidity", 55))),
        "oxygen":      float(payload.get("o", payload.get("oxygen", 8))),
        "ammonia":     float(payload.get("a", payload.get("ammonia", 5))),
        "turbidity":   float(payload.get("tb", payload.get("turbidity", 30))),
        "batteryLevel": float(payload.get("batt", payload.get("batteryLevel", 75))),
        "timestamp":   ts_iso,
        "sensor_id":   payload.get("d", payload.get("id", "unknown")),
        "_vendor":     "D",
        "_plot":       payload.get("p", payload.get("plot", "P1")),
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


NORMALIZER_MAP = {
    "A": normalize_vendor_a,
    "B": normalize_vendor_b,
    "C": normalize_vendor_c,
    "D": normalize_vendor_d,
}


def normalize(payload: dict) -> dict:
    """Normalize a payload according to its vendor (_vendor key)."""
    vendor = payload.get("_vendor", "A")
    fn = NORMALIZER_MAP.get(vendor, normalize_vendor_a)
    normalized = fn(payload)

    # Compute f1: completeness
    present = sum(1 for f in REQUIRED_FIELDS if normalized.get(f) is not None)
    normalized["_completeness"] = present / len(REQUIRED_FIELDS)

    return normalized
