"""
pipeline/validator.py
REAL SHACL validation using pyshacl against an actual rdflib Graph.
Implements 15 constraints (10 basic + 5 advanced).
Computes f1 (completeness) and f4 (plausibility) from SHACL report.
"""

import logging
import math
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyshacl
    from rdflib import Graph, Namespace, URIRef, Literal, BNode
    from rdflib.namespace import RDF, XSD
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False
    logger.warning("pyshacl/rdflib not available — falling back to Python validation")

# Namespace definitions
SOSA = Namespace("http://www.w3.org/ns/sosa/")
DQ = Namespace("http://example.org/dq#")
AGRI = Namespace("http://example.org/agri#")
EX = Namespace("http://example.org/")

# SHACL shapes file paths
_HERE = os.path.dirname(os.path.abspath(__file__))
SHAPES_BASIC = os.path.join(_HERE, "..", "semantic", "shacl_shapes.ttl")
SHAPES_ADVANCED = os.path.join(_HERE, "..", "semantic", "shacl_advanced.ttl")

# Valid ranges for agricultural measurements
VALID_RANGES = {
    "soilMoisture":      (  0.0, 100.0),
    "airTemperature":    (-40.0,  60.0),
    "soilTemperature":   (-10.0,  60.0),
    "soilPH":            (  0.0,  14.0),
    "illuminance":       (  0.0, 200000.0),
    "irrigationState":   (  0.0,   1.0),
    "fertilizationDose": (  0.0, 500.0),
    "batteryLevel":      (  0.0, 100.0),
    "qualityScore":      (  0.0,   1.0),
    # Legacy fields for backward compatibility
    "temperature": (-40.0,  60.0),
    "humidity":    (  0.0, 100.0),
    "moisture":    (  0.0, 100.0),
    "ph":          (  0.0,  14.0),
    "oxygen":      (  0.0,  20.0),
    "ammonia":     (  0.0,  10.0),
    "turbidity":   (  0.0, 500.0),
}

REQUIRED_FIELDS = ["temperature", "humidity", "moisture", "ph", "oxygen", "ammonia", "turbidity"]


def _sigmoid_boundary(value: float, low: float, high: float) -> float:
    """
    Soft sigmoid at boundaries: 1.0 at center, decreases at extremes.
    f4 contribution for a value within its range.
    """
    if low == high:
        return 1.0
    center = (high + low) / 2
    half_range = (high - low) / 2
    if half_range == 0:
        return 1.0
    normalized = abs(value - center) / half_range
    return 1.0 / (1.0 + math.exp(5 * (normalized - 0.8)))


def _observation_to_rdf(observation: dict) -> tuple:
    """
    Convert a normalized observation dict to an rdflib Graph
    with proper SOSA/SSN triples for SHACL validation.

    Returns:
        (Graph, obs_uri) tuple
    """
    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("xsd", XSD)

    # Create observation URI
    obs_id = observation.get("sensor_id", "unknown")
    ts_str = observation.get("timestamp", datetime.now(timezone.utc).isoformat())
    obs_uri = EX[f"obs-{obs_id}-{hash(ts_str) & 0xFFFFFF:06x}"]
    sensor_uri = EX[f"sensor-{obs_id}"]
    plot_id = observation.get("_plot", "P1")
    plot_uri = AGRI[f"Plot_{plot_id}"]
    prop_uri = AGRI["SoilMoisture"]

    # Core SOSA triples
    g.add((obs_uri, RDF.type, SOSA.Observation))
    g.add((obs_uri, SOSA.madeBySensor, sensor_uri))
    g.add((obs_uri, SOSA.observedProperty, prop_uri))
    g.add((obs_uri, SOSA.hasFeatureOfInterest, plot_uri))

    # Timestamp
    ts = ts_str.replace("Z", "+00:00") if isinstance(ts_str, str) else str(ts_str)
    try:
        datetime.fromisoformat(ts)
        g.add((obs_uri, SOSA.resultTime, Literal(ts, datatype=XSD.dateTime)))
    except ValueError:
        pass

    # Add measurement fields as dq: properties
    field_map = {
        "moisture":    DQ.soilMoisture,
        "temperature": DQ.airTemperature,
        "ph":          DQ.soilPH,
        "humidity":    DQ.humidity,
        "oxygen":      DQ.oxygen,
        "ammonia":     DQ.ammonia,
        "turbidity":   DQ.turbidity,
        # New article-spec fields
        "soilMoisture":      DQ.soilMoisture,
        "airTemperature":    DQ.airTemperature,
        "soilTemperature":   DQ.soilTemperature,
        "soilPH":            DQ.soilPH,
        "illuminance":       DQ.illuminance,
        "irrigationState":   DQ.irrigationState,
        "fertilizationDose": DQ.fertilizationDose,
        "batteryLevel":      DQ.batteryLevel,
        "qualityScore":      DQ.qualityScore,
    }
    for field, pred in field_map.items():
        val = observation.get(field)
        if val is not None:
            try:
                g.add((obs_uri, pred, Literal(float(val), datatype=XSD.decimal)))
            except (TypeError, ValueError):
                pass

    # Vendor info
    vendor = observation.get("_vendor")
    if vendor:
        g.add((obs_uri, DQ.vendorId, Literal(str(vendor), datatype=XSD.string)))

    # Stuck-at flag
    if observation.get("_stuck_at"):
        g.add((obs_uri, DQ.stuckAt, Literal(True, datatype=XSD.boolean)))

    # Missed report flag
    if observation.get("_missed_report"):
        g.add((obs_uri, DQ.missedReport, Literal(True, datatype=XSD.boolean)))

    # Seasonal anomaly flag
    if observation.get("_seasonal_anomaly"):
        g.add((obs_uri, DQ.seasonalAnomaly, Literal(True, datatype=XSD.boolean)))

    return g, obs_uri


def _load_shapes_graph() -> Graph:
    """Load combined SHACL shapes (basic + advanced)."""
    shapes_g = Graph()
    for path in [SHAPES_BASIC, SHAPES_ADVANCED]:
        if os.path.exists(path):
            shapes_g.parse(path, format="turtle")
        else:
            logger.warning("SHACL shapes file not found: %s", path)
    return shapes_g


class ValidationReport:
    def __init__(self):
        self.violations = []
        self.warnings = []

    def add_violation(self, field: str, shape: str, message: str, severity: str = "Violation"):
        self.violations.append({
            "field": field,
            "shape": shape,
            "message": message,
            "severity": severity,
        })

    def add_warning(self, field: str, shape: str, message: str):
        self.warnings.append({
            "field": field,
            "shape": shape,
            "message": message,
        })

    def is_valid(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict:
        return {
            "valid": self.is_valid(),
            "violation_count": len(self.violations),
            "warning_count": len(self.warnings),
            "violations": self.violations,
            "warnings": self.warnings,
        }


def _parse_shacl_report(report_graph: Graph, obs_uri) -> ValidationReport:
    """Parse pyshacl validation report graph into ValidationReport."""
    report = ValidationReport()
    SH = Namespace("http://www.w3.org/ns/shacl#")

    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        severity_node = report_graph.value(result, SH.resultSeverity)
        severity = str(severity_node).split("#")[-1] if severity_node else "Violation"

        message_node = report_graph.value(result, SH.resultMessage)
        message = str(message_node) if message_node else "SHACL constraint violation"

        path_node = report_graph.value(result, SH.resultPath)
        field = str(path_node).split("#")[-1].split("/")[-1] if path_node else "unknown"

        source_node = report_graph.value(result, SH.sourceShape)
        shape = str(source_node).split("#")[-1].split("/")[-1] if source_node else "UnknownShape"

        if severity in ("Warning", "Info"):
            report.add_warning(field, shape, message)
        else:
            report.add_violation(field, shape, message, severity)

    return report


def validate(observation: dict) -> "tuple[ValidationReport, float, float]":
    """
    Validate a normalized observation against 15 SHACL shapes using real pyshacl.

    Returns:
        (report, f1_completeness, f4_plausibility)
    """
    report = ValidationReport()

    if not PYSHACL_AVAILABLE:
        return _validate_fallback(observation)

    # Convert observation to RDF graph
    try:
        data_graph, obs_uri = _observation_to_rdf(observation)
    except Exception as exc:
        logger.warning("RDF conversion error: %s", exc)
        return _validate_fallback(observation)

    # Load SHACL shapes
    shapes_graph = _load_shapes_graph()

    if len(shapes_graph) == 0:
        logger.warning("No SHACL shapes loaded — falling back")
        return _validate_fallback(observation)

    # Run pyshacl validation
    try:
        conforms, results_graph, results_text = pyshacl.validate(
            data_graph,
            shacl_graph=shapes_graph,
            ont_graph=None,
            inference="none",
            abort_on_first=False,
            allow_warnings=True,
            meta_shacl=False,
            advanced=True,
            js=False,
            debug=False,
        )
        report = _parse_shacl_report(results_graph, obs_uri)
    except Exception as exc:
        logger.warning("pyshacl validation error: %s", exc)
        return _validate_fallback(observation)

    # Compute f1 (completeness)
    numeric_count = sum(1 for f in REQUIRED_FIELDS if observation.get(f) is not None)
    f1 = observation.get("_completeness", numeric_count / len(REQUIRED_FIELDS))

    # Compute f4 (plausibility) from SHACL results using sigmoid boundary
    plausibility_scores = []
    for field, (low, high) in VALID_RANGES.items():
        val = observation.get(field)
        if val is None:
            continue
        try:
            v = float(val)
            if v < low or v > high:
                plausibility_scores.append(0.0)
            else:
                plausibility_scores.append(_sigmoid_boundary(v, low, high))
        except (TypeError, ValueError):
            plausibility_scores.append(0.0)

    f4 = sum(plausibility_scores) / len(plausibility_scores) if plausibility_scores else 0.0

    # Reduce f4 by number of SHACL violations
    violation_penalty = len(report.violations) * 0.1
    f4 = max(0.0, f4 - violation_penalty)

    return report, f1, f4


def _validate_fallback(observation: dict) -> tuple:
    """
    Fallback Python-based validation when pyshacl is unavailable.
    Keeps the same logic as the original validator for compatibility.
    """
    report = ValidationReport()
    plausibility_scores = []

    # Shape 1: Structure
    if not observation.get("timestamp"):
        report.add_violation("timestamp", "ObservationStructure",
                              "Missing timestamp (resultTime required)")
    if not observation.get("sensor_id") and not observation.get("_vendor"):
        report.add_violation("sensor_id", "ObservationStructure",
                              "Missing sensor identifier")

    # Shapes 2-9: Range checks
    numeric_count = 0
    for field, (low, high) in VALID_RANGES.items():
        val = observation.get(field)
        if val is None:
            if field in REQUIRED_FIELDS:
                report.add_violation(field, "RangeCheck", f"Required field missing: {field}")
            plausibility_scores.append(0.0)
            continue
        try:
            v = float(val)
            numeric_count += 1
            if v < low or v > high:
                report.add_violation(
                    field, "RangeCheck",
                    f"{field}={v} out of range [{low}, {high}]"
                )
                plausibility_scores.append(0.0)
            else:
                plausibility_scores.append(_sigmoid_boundary(v, low, high))
        except (TypeError, ValueError):
            report.add_violation(field, "RangeCheck",
                                  f"{field} is not numeric: {val}")
            plausibility_scores.append(0.0)

    # Shape 10: Timestamp type
    ts = observation.get("timestamp")
    if ts:
        try:
            datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            report.add_violation("timestamp", "TimestampType",
                                  f"Invalid timestamp format: {ts}")

    # Shape 11: Timestamp not in future
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt > now:
                report.add_warning("timestamp", "TimestampNotFuture",
                                    f"Timestamp in the future: {ts}")
        except ValueError:
            pass

    # Shape 13: Stuck-at
    if observation.get("_stuck_at"):
        report.add_violation("_stuck_at", "StuckAtDetection",
                              "Stuck-at sensor detected (same value repeated)")

    # Shape 15: Vendor completeness
    if not observation.get("_vendor"):
        report.add_violation("_vendor", "ProvenanceCompleteness",
                              "Missing vendor identifier")

    # Compute f1
    base_count = sum(1 for f in REQUIRED_FIELDS if observation.get(f) is not None)
    f1 = observation.get("_completeness", base_count / len(REQUIRED_FIELDS))

    # Compute f4
    f4 = sum(plausibility_scores) / len(plausibility_scores) if plausibility_scores else 0.0

    return report, f1, f4
