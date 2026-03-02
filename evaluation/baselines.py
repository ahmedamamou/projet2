"""
evaluation/baselines.py
3 real comparison baselines:
  B1-ETL:       JSON → Python dict + if/else rules. NO RDF, NO SHACL.
  B2-RDF-naive: RML → RDF, NO SHACL, NO normalization, NO quality scoring.
  B3-SHACL-no-Q: RML → RDF → SHACL validation, but NO quality-weighted confidence.
"""

import time
import copy
import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def baseline_b1_etl(observations: list) -> tuple:
    """
    B1 — Classic ETL: JSON → Python dict processing → SQLite/dict-based storage.
    Uses if/else rules for alerts. NO RDF, NO SHACL.
    """
    t0 = time.perf_counter()
    result = []
    alerts = []

    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B1_ETL"

        # Simple if/else rules (no quality score formula)
        flags = []
        moisture = processed.get("moisture", processed.get("soilMoisture"))
        temp = processed.get("temperature", processed.get("airTemperature"))
        ph = processed.get("ph", processed.get("soilPH"))

        if moisture is not None:
            if float(moisture) < 0 or float(moisture) > 100:
                flags.append(f"moisture_out_of_range:{moisture}")
            elif float(moisture) < 20:
                alerts.append({"type": "low_moisture", "value": moisture})

        if temp is not None:
            if float(temp) < -40 or float(temp) > 60:
                flags.append(f"temperature_out_of_range:{temp}")

        if ph is not None:
            if float(ph) < 0 or float(ph) > 14:
                flags.append(f"ph_out_of_range:{ph}")

        processed["_flags"] = [{"type": f, "repaired": False} for f in flags]
        processed["_Q"] = 0.5 if flags else 1.0
        processed["_alerts"] = alerts
        result.append(processed)

    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def baseline_b2_rdf_naive(observations: list) -> tuple:
    """
    B2 — Naive RDF: RML lifting → RDF graph, NO SHACL validation,
    NO normalization, NO quality scoring. Direct SPARQL queries.
    """
    from mapping.rml_runner import run_rml_mapping, merge_graphs

    t0 = time.perf_counter()
    result = []
    graphs = []

    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B2_RDF_naive"

        # Perform RML lifting (no normalization, no SHACL)
        vendor = processed.get("_vendor", "A")
        g = run_rml_mapping(processed, vendor)
        if g is not None:
            graphs.append(g)

        # Assign uniform quality score (no calculation)
        processed["_Q"] = 0.8
        processed["_quality_score"] = {
            "Q": 0.8,
            "f1_completeness": 1.0,
            "f2_unit_confidence": 0.8,
            "f3_freshness": 1.0,
            "f4_plausibility": 0.8,
            "f5_reliability": 0.8,
        }
        result.append(processed)

    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def baseline_b3_shacl_no_q(observations: list) -> tuple:
    """
    B3 — SHACL without quality scoring: RML → RDF → SHACL validation → repair/flag,
    but alerts triggered WITHOUT quality-weighted confidence.
    All conforming observations treated equally (binary: valid=1, invalid=0).
    """
    from pipeline.validator import validate

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B3_SHACL_no_Q"
        try:
            report, f1, f4 = validate(processed)
            processed["_validation"] = report.to_dict()
            processed["_f4_plausibility"] = f4
            # Binary quality score: valid=1, invalid=0 (no weighted formula)
            processed["_Q"] = 1.0 if report.is_valid() else 0.0
            processed["_quality_score"] = {
                "Q": processed["_Q"],
                "f1_completeness": f1,
                "f4_plausibility": f4,
            }
        except Exception as exc:
            logger.warning("B3 validation error: %s", exc)
            processed["_Q"] = 0.5
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def run_all_baselines(observations: list) -> dict:
    """Run all 3 baselines on the same batch of observations."""
    return {
        "B1_ETL":        baseline_b1_etl(observations),
        "B2_RDF_naive":  baseline_b2_rdf_naive(observations),
        "B3_SHACL_no_Q": baseline_b3_shacl_no_q(observations),
    }
