"""
pipeline/vendor_router.py
Transforme les données uniformes en 4 formats vendor hétérogènes.
Simule l'hétérogénéité des capteurs IoT réels.
"""

import math
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def route_to_vendor_a(data: dict) -> dict:
    """
    Vendor A : JSON clair, unités en %, timestamp ISO 8601.
    """
    return {
        "humidity_pct": float(data.get("humidity", 55.0)),
        "moisture_pct": float(data.get("moisture", 35.0)),
        "temperature_c": float(data.get("temperature", 25.0)),
        "ph_value": float(data.get("ph", 7.0)),
        "oxygen_mgl": float(data.get("oxygen", 8.0)),
        "ammonia_mgl": float(data.get("ammonia", 5.0)),
        "turbidity_ntu": float(data.get("turbidity", 30.0)),
        "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sensor_id": data.get("node_id", "node_2"),
        "_vendor": "A",
    }


def route_to_vendor_b(data: dict) -> dict:
    """
    Vendor B : epoch timestamp ms, fraction 0-1, température °F.
    """
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            epoch_ms = int(dt.timestamp() * 1000)
        except ValueError:
            epoch_ms = int(time.time() * 1000)
    else:
        epoch_ms = int(ts)

    temp_c = float(data.get("temperature", 25.0))
    temp_f = temp_c * 9 / 5 + 32

    return {
        "hum": round(float(data.get("humidity", 55.0)) / 100, 4),
        "moi": round(float(data.get("moisture", 35.0)) / 100, 4),
        "temp_f": round(temp_f, 2),
        "ph": float(data.get("ph", 7.0)),
        "oxy": float(data.get("oxygen", 8.0)),
        "amm": float(data.get("ammonia", 5.0)),
        "turb": float(data.get("turbidity", 30.0)),
        "ts": epoch_ms,
        "node": data.get("node_id", "node_3"),
        "_vendor": "B",
    }


def route_to_vendor_c(data: dict) -> dict:
    """
    Vendor C : JSON imbriqué, valeurs en permille (‰).
    """
    return {
        "data": {
            "env": {
                "humidity_pm": round(float(data.get("humidity", 55.0)) * 10, 1),
                "temperature_c": float(data.get("temperature", 25.0)),
            },
            "soil": {
                "moisture_pm": round(float(data.get("moisture", 35.0)) * 10, 1),
                "ph": float(data.get("ph", 7.0)),
            },
            "water": {
                "oxygen_mgl": float(data.get("oxygen", 8.0)),
                "ammonia_mgl": float(data.get("ammonia", 5.0)),
                "turbidity_ntu": float(data.get("turbidity", 30.0)),
            },
        },
        "meta": {
            "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "device": data.get("node_id", "node_4"),
        },
        "_vendor": "C",
    }


def route_to_vendor_d(data: dict) -> dict:
    """
    Vendor D : format compact minimal, clés courtes, entiers.
    """
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            epoch_s = int(dt.timestamp())
        except ValueError:
            epoch_s = int(time.time())
    else:
        epoch_s = int(ts)

    return {
        "h": int(round(float(data.get("humidity", 55.0)))),
        "m": int(round(float(data.get("moisture", 35.0)))),
        "t": int(round(float(data.get("temperature", 25.0)))),
        "p": int(round(float(data.get("ph", 7.0)))),
        "o": int(round(float(data.get("oxygen", 8.0)))),
        "a": int(round(float(data.get("ammonia", 5.0)))),
        "tb": int(round(float(data.get("turbidity", 30.0)))),
        "ts": epoch_s,
        "id": data.get("node_id", "n5"),
        "_vendor": "D",
    }


# Mapping nœud → fonction vendor
NODE_ROUTER = {
    "node_2": route_to_vendor_a,
    "node_3": route_to_vendor_b,
    "node_4": route_to_vendor_c,
    "node_5": route_to_vendor_d,
    "node_6": route_to_vendor_a,
}

VENDOR_ROUTER = {
    "A": route_to_vendor_a,
    "B": route_to_vendor_b,
    "C": route_to_vendor_c,
    "D": route_to_vendor_d,
}


def route(data: dict) -> dict:
    """
    Route les données vers le format vendor approprié selon le node_id ou vendor.
    """
    node_id = data.get("node_id", "node_2")
    vendor = data.get("vendor", "A")

    router_fn = NODE_ROUTER.get(node_id) or VENDOR_ROUTER.get(vendor, route_to_vendor_a)
    routed = router_fn(data)
    routed["_original_node"] = node_id
    return routed
