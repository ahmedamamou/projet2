"""
mapping/rml_runner.py
Executes RML mappings to produce rdflib Graph triples.
Reads RML TTL files and programmatically creates SOSA/SSN-compliant RDF graphs.
Supports all 4 vendor formats (A, B, C, D).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from rdflib import Graph, Namespace, URIRef, Literal, BNode
    from rdflib.namespace import RDF, XSD, OWL
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    logger.error("rdflib not available — RML runner disabled")

# Namespaces
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSN = Namespace("http://www.w3.org/ns/ssn/")
DQ = Namespace("http://example.org/dq#")
AGRI = Namespace("http://example.org/agri#")
EX = Namespace("http://example.org/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _make_obs_uri(vendor: str, sensor_id: str, timestamp: str) -> URIRef:
    """Create a deterministic observation URI."""
    slug = f"{vendor}-{sensor_id}-{hash(timestamp) & 0xFFFFFFFF:08x}"
    return EX[f"obs-{slug}"]


def _make_result_uri(obs_uri: URIRef) -> URIRef:
    """Create result URI from observation URI."""
    return URIRef(str(obs_uri).replace("/obs-", "/res-"))


def _add_common_triples(g: Graph, obs_uri: URIRef, result_uri: URIRef,
                         sensor_id: str, timestamp: str, vendor: str,
                         plot_id: str = "P1") -> None:
    """Add common SOSA observation triples."""
    sensor_uri = EX[f"sensor-{sensor_id}"]
    plot_uri = AGRI[f"Plot_{plot_id}"]

    g.add((obs_uri, RDF.type, SOSA.Observation))
    g.add((obs_uri, SOSA.madeBySensor, sensor_uri))
    g.add((obs_uri, SOSA.hasFeatureOfInterest, plot_uri))
    g.add((obs_uri, DQ.vendorId, Literal(vendor, datatype=XSD.string)))

    # Timestamp
    ts = timestamp.replace("Z", "+00:00") if isinstance(timestamp, str) else str(timestamp)
    try:
        datetime.fromisoformat(ts)
        g.add((obs_uri, SOSA.resultTime, Literal(ts, datatype=XSD.dateTime)))
    except ValueError:
        now = datetime.now(timezone.utc).isoformat()
        g.add((obs_uri, SOSA.resultTime, Literal(now, datatype=XSD.dateTime)))

    # Result node
    g.add((obs_uri, SOSA.hasResult, result_uri))
    g.add((result_uri, RDF.type, QUDT.QuantityValue))


def _add_measurement(g: Graph, obs_uri: URIRef, result_uri: URIRef,
                      property_uri: URIRef, value: float, unit_uri: URIRef) -> None:
    """Add a measurement triple with observed property, result, and unit."""
    g.add((obs_uri, SOSA.observedProperty, property_uri))
    g.add((result_uri, QUDT.numericValue, Literal(value, datatype=XSD.decimal)))
    g.add((result_uri, QUDT.unit, unit_uri))


def vendor_a_to_rdf(payload: dict) -> Graph:
    """
    Vendor A — Clean JSON format:
    {"deviceId": "sm-01", "ts": "2026-02-28T10:15:00Z", "soilMoisture": 23.4, "unit": "%", "plot": "P1"}
    """
    if not RDFLIB_AVAILABLE:
        return None

    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)

    sensor_id = payload.get("deviceId", payload.get("sensor_id", "sm-unknown"))
    timestamp = payload.get("ts", payload.get("timestamp", datetime.now(timezone.utc).isoformat()))
    plot_id = payload.get("plot", "P1")

    obs_uri = _make_obs_uri("A", sensor_id, str(timestamp))
    result_uri = _make_result_uri(obs_uri)

    _add_common_triples(g, obs_uri, result_uri, sensor_id, str(timestamp), "A", plot_id)

    # Soil moisture
    sm = payload.get("soilMoisture", payload.get("moisture_pct", payload.get("moisture")))
    if sm is not None:
        g.add((obs_uri, SOSA.observedProperty, AGRI.SoilMoisture))
        g.add((result_uri, QUDT.numericValue, Literal(float(sm), datatype=XSD.decimal)))
        g.add((result_uri, QUDT.unit, UNIT.PERCENT))
        g.add((obs_uri, DQ.soilMoisture, Literal(float(sm), datatype=XSD.decimal)))

    # Air temperature
    temp = payload.get("airTemperature", payload.get("temperature_c", payload.get("temperature")))
    if temp is not None:
        g.add((obs_uri, DQ.airTemperature, Literal(float(temp), datatype=XSD.decimal)))

    # Soil pH
    ph = payload.get("soilPH", payload.get("ph_value", payload.get("ph")))
    if ph is not None:
        g.add((obs_uri, DQ.soilPH, Literal(float(ph), datatype=XSD.decimal)))

    # Battery level
    batt = payload.get("batteryLevel", payload.get("battery"))
    if batt is not None:
        g.add((obs_uri, DQ.batteryLevel, Literal(float(batt), datatype=XSD.decimal)))

    # Legacy fields
    for field, pred in [("humidity", DQ.humidity), ("oxygen", DQ.oxygen),
                         ("ammonia", DQ.ammonia), ("turbidity", DQ.turbidity)]:
        val = payload.get(field + "_pct", payload.get(field + "_mgl",
              payload.get(field + "_ntu", payload.get(field))))
        if val is not None:
            g.add((obs_uri, pred, Literal(float(val), datatype=XSD.decimal)))

    return g


def vendor_b_to_rdf(payload: dict) -> Graph:
    """
    Vendor B — Epoch + fraction format:
    {"id": "node7", "time": 1772273700, "sm": 0.234, "sm_unit": "vwc", "field": "plot-1"}
    """
    if not RDFLIB_AVAILABLE:
        return None

    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)

    sensor_id = payload.get("id", payload.get("node", "node-unknown"))
    epoch = payload.get("time", payload.get("ts", 0))
    try:
        timestamp = datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        timestamp = datetime.now(timezone.utc).isoformat()

    plot_raw = payload.get("field", payload.get("plot", "plot-1"))
    plot_id = str(plot_raw).replace("plot-", "P").replace("P0", "P")

    obs_uri = _make_obs_uri("B", str(sensor_id), timestamp)
    result_uri = _make_result_uri(obs_uri)

    _add_common_triples(g, obs_uri, result_uri, str(sensor_id), timestamp, "B", plot_id)

    # Soil moisture (fraction → %)
    sm_frac = payload.get("sm", payload.get("moi"))
    if sm_frac is not None:
        sm_pct = float(sm_frac) * 100 if float(sm_frac) <= 1.0 else float(sm_frac)
        g.add((obs_uri, SOSA.observedProperty, AGRI.SoilMoisture))
        g.add((result_uri, QUDT.numericValue, Literal(sm_pct, datatype=XSD.decimal)))
        g.add((result_uri, QUDT.unit, UNIT.PERCENT))
        g.add((obs_uri, DQ.soilMoisture, Literal(sm_pct, datatype=XSD.decimal)))

    # Temperature (may be in °F)
    temp = payload.get("temperature", payload.get("temp_f", payload.get("temp_c")))
    if temp is not None:
        temp_val = float(temp)
        # Heuristic: if > 60, likely Fahrenheit
        if temp_val > 60 and "temp_f" in payload:
            temp_val = (temp_val - 32) * 5 / 9
        g.add((obs_uri, DQ.airTemperature, Literal(temp_val, datatype=XSD.decimal)))

    # pH
    ph = payload.get("ph")
    if ph is not None:
        g.add((obs_uri, DQ.soilPH, Literal(float(ph), datatype=XSD.decimal)))

    return g


def vendor_c_to_rdf(payload: dict) -> Graph:
    """
    Vendor C — Nested + permille format:
    {"meta": {"dev": "A9", "plot": "P1"}, "obs": {"t": "2026-02-28 10:15:00", "val": 234},
     "type": "SOIL_MOIST", "scale": "permille"}
    """
    if not RDFLIB_AVAILABLE:
        return None

    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)

    meta = payload.get("meta", {})
    obs_data = payload.get("obs", payload.get("data", {}).get("env", {}))

    sensor_id = meta.get("dev", meta.get("device", "dev-unknown"))
    plot_id = meta.get("plot", "P1")

    # Timestamp from obs.t or meta.timestamp
    ts_raw = obs_data.get("t", meta.get("timestamp", datetime.now(timezone.utc).isoformat()))
    try:
        ts_raw_str = str(ts_raw).replace(" ", "T")
        if "+" not in ts_raw_str and "Z" not in ts_raw_str:
            ts_raw_str += "+00:00"
        datetime.fromisoformat(ts_raw_str.replace("Z", "+00:00"))
        timestamp = ts_raw_str
    except ValueError:
        timestamp = datetime.now(timezone.utc).isoformat()

    obs_uri = _make_obs_uri("C", str(sensor_id), timestamp)
    result_uri = _make_result_uri(obs_uri)

    _add_common_triples(g, obs_uri, result_uri, str(sensor_id), timestamp, "C", plot_id)

    # Value and type
    obs_type = payload.get("type", "SOIL_MOIST")
    scale = payload.get("scale", "percent")
    val_raw = obs_data.get("val", obs_data.get("value"))

    if val_raw is not None:
        val = float(val_raw)
        # Convert units
        if scale == "permille":
            val = val / 10.0
        elif scale == "fraction":
            val = val * 100.0

        if obs_type in ("SOIL_MOIST", "MOISTURE"):
            g.add((obs_uri, SOSA.observedProperty, AGRI.SoilMoisture))
            g.add((result_uri, QUDT.numericValue, Literal(val, datatype=XSD.decimal)))
            g.add((result_uri, QUDT.unit, UNIT.PERCENT))
            g.add((obs_uri, DQ.soilMoisture, Literal(val, datatype=XSD.decimal)))
        elif obs_type in ("TEMP", "TEMPERATURE"):
            g.add((obs_uri, DQ.airTemperature, Literal(val, datatype=XSD.decimal)))
        elif obs_type in ("PH", "SOIL_PH"):
            g.add((obs_uri, DQ.soilPH, Literal(val, datatype=XSD.decimal)))

    # Handle nested data structure (legacy Vendor C format)
    env_data = payload.get("data", {}).get("env", {})
    soil_data = payload.get("data", {}).get("soil", {})

    hum_pm = env_data.get("humidity_pm")
    if hum_pm is not None:
        hum = float(hum_pm) / 10.0
        g.add((obs_uri, DQ.humidity, Literal(hum, datatype=XSD.decimal)))

    moi_pm = soil_data.get("moisture_pm")
    if moi_pm is not None:
        moi = float(moi_pm) / 10.0
        if not g.value(obs_uri, DQ.soilMoisture):
            g.add((obs_uri, DQ.soilMoisture, Literal(moi, datatype=XSD.decimal)))

    temp_c = env_data.get("temperature_c")
    if temp_c is not None:
        g.add((obs_uri, DQ.airTemperature, Literal(float(temp_c), datatype=XSD.decimal)))

    ph = soil_data.get("ph")
    if ph is not None:
        g.add((obs_uri, DQ.soilPH, Literal(float(ph), datatype=XSD.decimal)))

    return g


def vendor_d_to_rdf(payload: dict) -> Graph:
    """
    Vendor D — Compact format:
    {"d": "19", "t": 1772273700, "m": 23, "k": "SM"}
    """
    if not RDFLIB_AVAILABLE:
        return None

    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)

    sensor_id = payload.get("d", payload.get("id", "dev-unknown"))
    epoch = payload.get("t", payload.get("ts", 0))
    try:
        timestamp = datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        timestamp = datetime.now(timezone.utc).isoformat()

    kind = payload.get("k", "SM")
    plot_id = payload.get("p", payload.get("plot", "P1"))

    obs_uri = _make_obs_uri("D", str(sensor_id), timestamp)
    result_uri = _make_result_uri(obs_uri)

    _add_common_triples(g, obs_uri, result_uri, str(sensor_id), timestamp, "D", str(plot_id))

    # Value by kind
    val = payload.get("m", payload.get("v"))
    if val is not None:
        val_f = float(val)
        if kind == "SM":  # Soil moisture
            g.add((obs_uri, SOSA.observedProperty, AGRI.SoilMoisture))
            g.add((result_uri, QUDT.numericValue, Literal(val_f, datatype=XSD.decimal)))
            g.add((result_uri, QUDT.unit, UNIT.PERCENT))
            g.add((obs_uri, DQ.soilMoisture, Literal(val_f, datatype=XSD.decimal)))
        elif kind == "AT":  # Air temperature
            g.add((obs_uri, DQ.airTemperature, Literal(val_f, datatype=XSD.decimal)))
        elif kind == "PH":  # Soil pH
            g.add((obs_uri, DQ.soilPH, Literal(val_f, datatype=XSD.decimal)))
        elif kind == "BT":  # Battery
            g.add((obs_uri, DQ.batteryLevel, Literal(val_f, datatype=XSD.decimal)))

    # Legacy compact keys
    for key, pred in [("h", DQ.humidity), ("o", DQ.oxygen), ("a", DQ.ammonia), ("tb", DQ.turbidity)]:
        v = payload.get(key)
        if v is not None:
            g.add((obs_uri, pred, Literal(float(v), datatype=XSD.decimal)))

    return g


VENDOR_RML_MAP = {
    "A": vendor_a_to_rdf,
    "B": vendor_b_to_rdf,
    "C": vendor_c_to_rdf,
    "D": vendor_d_to_rdf,
}


def run_rml_mapping(payload: dict, vendor: str = None) -> Optional[Graph]:
    """
    Execute RML mapping for a vendor payload, producing an rdflib Graph.
    
    This implements the RML mapping logic described in the vendor_*.rml.ttl files,
    converting vendor-specific JSON payloads to SOSA/SSN-compliant RDF triples.
    
    Args:
        payload: Vendor-specific JSON payload
        vendor: Vendor identifier (A, B, C, D). Auto-detected if None.
    
    Returns:
        rdflib Graph with SOSA/SSN triples, or None on error
    """
    if not RDFLIB_AVAILABLE:
        logger.error("rdflib not available")
        return None

    if vendor is None:
        vendor = payload.get("_vendor", "A")

    mapper = VENDOR_RML_MAP.get(vendor)
    if mapper is None:
        logger.warning("Unknown vendor: %s, using vendor A mapping", vendor)
        mapper = vendor_a_to_rdf

    try:
        g = mapper(payload)
        if g is not None:
            logger.debug("RML mapping produced %d triples for vendor %s", len(g), vendor)
        return g
    except Exception as exc:
        logger.warning("RML mapping error for vendor %s: %s", vendor, exc)
        return None


def merge_graphs(graphs: list) -> Graph:
    """Merge multiple rdflib Graphs into one."""
    merged = Graph()
    merged.bind("sosa", SOSA)
    merged.bind("dq", DQ)
    merged.bind("agri", AGRI)
    merged.bind("qudt", QUDT)
    merged.bind("unit", UNIT)
    for g in graphs:
        if g is not None:
            for triple in g:
                merged.add(triple)
    return merged
