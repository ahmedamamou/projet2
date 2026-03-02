"""
pipeline/vendor_router.py
Routes sensor data to 4 vendor-specific formats as defined in the article (section 9).
Vendor A: Clean JSON | Vendor B: Epoch+fraction | Vendor C: Nested+permille | Vendor D: Compact
"""

import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def route_to_vendor_a(data: dict) -> dict:
    """
    Vendor A — Clean JSON (article spec):
    {"deviceId": "sm-01", "ts": "2026-02-28T10:15:00Z", "soilMoisture": 23.4, "unit": "%", "plot": "P1"}
    """
    return {
        "deviceId":     data.get("node_id", "sm-01"),
        "ts":           data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "soilMoisture": float(data.get("soilMoisture", data.get("moisture", 35.0))),
        "airTemperature": float(data.get("airTemperature", data.get("temperature", 22.0))),
        "soilPH":       float(data.get("soilPH", data.get("ph", 6.8))),
        "batteryLevel": float(data.get("batteryLevel", 75.0)),
        "unit":         "%",
        "plot":         data.get("plot", "P1"),
        "_vendor":      "A",
    }


def route_to_vendor_b(data: dict) -> dict:
    """
    Vendor B — Epoch + fraction (article spec):
    {"id": "node7", "time": 1772273700, "sm": 0.234, "sm_unit": "vwc", "field": "plot-1"}
    """
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        epoch = int(dt.timestamp())
    except ValueError:
        epoch = int(time.time())

    moisture = float(data.get("soilMoisture", data.get("moisture", 35.0)))
    plot_id = data.get("plot", "P1")
    plot_num = plot_id.replace("P", "") if isinstance(plot_id, str) else "1"

    return {
        "id":      data.get("node_id", "node7"),
        "time":    epoch,
        "sm":      round(moisture / 100.0, 4),   # fraction VWC
        "sm_unit": "vwc",
        "field":   f"plot-{plot_num}",
        "temp_c":  float(data.get("airTemperature", data.get("temperature", 22.0))),
        "ph":      float(data.get("soilPH", data.get("ph", 6.8))),
        "battery": float(data.get("batteryLevel", 75.0)),
        "_vendor": "B",
    }


def route_to_vendor_c(data: dict) -> dict:
    """
    Vendor C — Nested + permille (article spec):
    {"meta": {"dev": "A9", "plot": "P1"}, "obs": {"t": "2026-02-28 10:15:00", "val": 234},
     "type": "SOIL_MOIST", "scale": "permille"}
    """
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    ts_fmt = str(ts).replace("T", " ").replace("+00:00", "").replace("Z", "")

    moisture = float(data.get("soilMoisture", data.get("moisture", 35.0)))
    return {
        "meta": {
            "dev":  data.get("node_id", "A9"),
            "plot": data.get("plot", "P1"),
        },
        "obs": {
            "t":   ts_fmt,
            "val": int(moisture * 10),   # permille
        },
        "type":   "SOIL_MOIST",
        "scale":  "permille",
        "airTemperature": float(data.get("airTemperature", data.get("temperature", 22.0))),
        "soilPH": float(data.get("soilPH", data.get("ph", 6.8))),
        "_vendor": "C",
    }


def route_to_vendor_d(data: dict) -> dict:
    """
    Vendor D — Compact (article spec):
    {"d": "19", "t": 1772273700, "m": 23, "k": "SM"}
    """
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        epoch = int(dt.timestamp())
    except ValueError:
        epoch = int(time.time())

    moisture = float(data.get("soilMoisture", data.get("moisture", 35.0)))
    ph = float(data.get("soilPH", data.get("ph", 6.8)))

    return {
        "d":       data.get("node_id", "19"),
        "t":       epoch,
        "m":       int(round(moisture)),
        "k":       "SM",
        "temp":    int(round(float(data.get("airTemperature", data.get("temperature", 22.0))))),
        "ph_x10":  int(round(ph * 10)),
        "batt":    int(round(float(data.get("batteryLevel", 75.0)))),
        "_vendor": "D",
    }


NODE_ROUTER = {
    "node_1": route_to_vendor_b,
    "node_2": route_to_vendor_c,
    "node_3": route_to_vendor_d,
    "node_4": route_to_vendor_a,
    "node_5": route_to_vendor_b,
    "node_6": route_to_vendor_c,
    "node_7": route_to_vendor_d,
    "node_8": route_to_vendor_a,
}

VENDOR_ROUTER = {
    "A": route_to_vendor_a,
    "B": route_to_vendor_b,
    "C": route_to_vendor_c,
    "D": route_to_vendor_d,
}


def route(data: dict) -> dict:
    """Route data to the appropriate vendor format."""
    node_id = data.get("node_id", "node_4")
    vendor = data.get("vendor", data.get("_vendor", "A"))

    router_fn = NODE_ROUTER.get(node_id) or VENDOR_ROUTER.get(vendor, route_to_vendor_a)
    routed = router_fn(data)
    routed["_original_node"] = node_id
    return routed
