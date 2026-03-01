"""
pipeline/validator.py
Validation SHACL-like des observations normalisées.
Implémente 15 contraintes (10 basiques + 5 avancées).
Calcule f4 (plausibilité) et f1 (complétude via violations).
"""

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Plages valides pour chaque mesure
VALID_RANGES = {
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
    Sigmoïde douce aux bornes : 1.0 au centre, décroît aux extrémités.
    f4 contribution pour une valeur dans sa plage.
    """
    if low == high:
        return 1.0
    center = (high + low) / 2
    half_range = (high - low) / 2
    if half_range == 0:
        return 1.0
    normalized = abs(value - center) / half_range
    return 1.0 / (1.0 + math.exp(5 * (normalized - 0.8)))


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


def validate(observation: dict) -> tuple[ValidationReport, float, float]:
    """
    Valide une observation normalisée contre les 15 shapes SHACL.

    Returns:
        (report, f1_completeness, f4_plausibility)
    """
    report = ValidationReport()
    plausibility_scores = []

    # ── SHAPE 1 : Structure (timestamp présent) ──────────────────────────────
    if not observation.get("timestamp"):
        report.add_violation("timestamp", "ObservationStructure",
                              "Timestamp manquant (resultTime requis)")

    # ── SHAPE 2 : Valeur numérique présente ──────────────────────────────────
    numeric_count = 0
    for field in REQUIRED_FIELDS:
        val = observation.get(field)
        if val is None:
            report.add_violation(field, "ResultValue",
                                  f"Champ requis manquant : {field}")
        else:
            numeric_count += 1

    # ── SHAPES 3-9 : Plages de valeurs ───────────────────────────────────────
    shape_names = {
        "temperature": "TemperatureRange",
        "humidity":    "HumidityRange",
        "moisture":    "MoistureRange",
        "ph":          "PHRange",
        "oxygen":      "OxygenRange",
        "ammonia":     "AmmoniaRange",
        "turbidity":   "TurbidityRange",
    }
    for field, (low, high) in VALID_RANGES.items():
        val = observation.get(field)
        if val is None:
            plausibility_scores.append(0.0)
            continue
        try:
            v = float(val)
            if v < low or v > high:
                report.add_violation(
                    field,
                    shape_names.get(field, "RangeCheck"),
                    f"{field}={v} hors plage [{low}, {high}]"
                )
                plausibility_scores.append(0.0)
            else:
                plausibility_scores.append(_sigmoid_boundary(v, low, high))
        except (TypeError, ValueError):
            report.add_violation(field, shape_names.get(field, "RangeCheck"),
                                  f"{field} n'est pas numérique : {val}")
            plausibility_scores.append(0.0)

    # ── SHAPE 10 : Type timestamp ─────────────────────────────────────────────
    ts = observation.get("timestamp")
    if ts:
        try:
            datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            report.add_violation("timestamp", "TimestampType",
                                  f"Timestamp non valide (xsd:dateTime attendu) : {ts}")

    # ── SHAPE 11 (avancé) : Timestamp pas dans le futur ──────────────────────
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt > now:
                report.add_warning("timestamp", "TimestampNotFuture",
                                    f"Timestamp dans le futur : {ts}")
        except ValueError:
            pass

    # ── SHAPE 12 (avancé) : Cohérence spatiale ───────────────────────────────
    hum = observation.get("humidity")
    moi = observation.get("moisture")
    if hum is not None and float(hum) > 100:
        report.add_warning("humidity", "SpatialCoherence",
                            f"Humidité > 100% : {hum}")
    if moi is not None and float(moi) > 100:
        report.add_warning("moisture", "SpatialCoherence",
                            f"Humidité sol > 100% : {moi}")

    # ── SHAPE 13 (avancé) : Stuck-at ─────────────────────────────────────────
    if observation.get("_stuck_at"):
        report.add_violation("_stuck_at", "StuckAtDetection",
                              "Capteur bloqué détecté (même valeur répétée)")

    # ── SHAPE 14 (avancé) : Cohérence croisée pH/oxygène ─────────────────────
    ph = observation.get("ph")
    oxy = observation.get("oxygen")
    if ph is not None and oxy is not None:
        if 6.5 <= float(ph) <= 7.5 and float(oxy) < 2.0:
            report.add_warning("oxygen", "CrossProperty",
                                f"pH neutre ({ph}) mais oxygène très faible ({oxy} mg/L)")

    # ── SHAPE 15 (avancé) : Complétude provenance ────────────────────────────
    if not observation.get("_vendor"):
        report.add_violation("_vendor", "ProvenanceCompleteness",
                              "Identifiant vendor manquant")

    # ── Calcul f1 (complétude) ───────────────────────────────────────────────
    f1 = observation.get("_completeness", numeric_count / len(REQUIRED_FIELDS))

    # ── Calcul f4 (plausibilité) ─────────────────────────────────────────────
    f4 = sum(plausibility_scores) / len(plausibility_scores) if plausibility_scores else 0.0

    return report, f1, f4
