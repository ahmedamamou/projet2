"""
pipeline/provenance.py
Traçabilité PROV-O : source vendor, template utilisé, conversions appliquées.
"""

import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROV_BASE = "http://example.org/prov/"
AGENT_BASE = "http://example.org/agent/"
ACTIVITY_BASE = "http://example.org/activity/"


def create_provenance(observation: dict) -> dict:
    """
    Crée un enregistrement de provenance PROV-O pour une observation.
    """
    prov_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    vendor = observation.get("_vendor", "unknown")
    sensor_id = observation.get("sensor_id", "unknown")
    conversions = observation.get("_conversions", [])
    unit_confidence = observation.get("_unit_confidence", 0.8)
    repairs = observation.get("_repairs", [])
    flags = observation.get("_flags", [])
    q_score = observation.get("_Q", 0.0)

    provenance = {
        "id": prov_id,
        "uri": f"{PROV_BASE}{prov_id}",
        "type": "prov:Entity",
        "generated_at": now,
        "agent": {
            "uri": f"{AGENT_BASE}{vendor}",
            "label": f"Vendor {vendor} sensor {sensor_id}",
            "vendor_id": vendor,
            "sensor_id": sensor_id,
        },
        "activity": {
            "uri": f"{ACTIVITY_BASE}pipeline/{prov_id}",
            "label": "AgriSem semantic mediation pipeline",
            "started_at": now,
            "steps": [
                "parse_cooja",
                "vendor_routing",
                "unit_normalization",
                "shacl_validation",
                "repair_flagging",
                "quality_scoring",
                "kg_insertion",
                "quality_aware_decision",
            ],
        },
        "transformations": {
            "vendor_format": _get_vendor_format(vendor),
            "unit_conversions": conversions,
            "unit_confidence": unit_confidence,
            "repairs_applied": repairs,
            "anomalies_flagged": flags,
        },
        "quality": {
            "Q": q_score,
            "factors": observation.get("_quality_score", {}),
        },
        "source": {
            "node_id": observation.get("_original_node", sensor_id),
            "raw_data_available": True,
        },
    }

    return provenance


def _get_vendor_format(vendor: str) -> str:
    formats = {
        "A": "JSON clair, unités %, timestamp ISO 8601",
        "B": "Epoch timestamp ms, fraction 0-1, température °F",
        "C": "JSON imbriqué, valeurs permille (‰)",
        "D": "Format compact, clés courtes, entiers",
    }
    return formats.get(vendor, "Format inconnu")


def to_turtle(provenance: dict) -> str:
    """
    Sérialise le provenance record en Turtle (PROV-O simplifié).
    """
    uri = provenance["uri"]
    agent_uri = provenance["agent"]["uri"]
    activity_uri = provenance["activity"]["uri"]
    ts = provenance["generated_at"]
    vendor = provenance["agent"]["vendor_id"]
    sensor = provenance["agent"]["sensor_id"]
    q = provenance["quality"]["Q"]

    lines = [
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix dq:   <http://example.org/dq#> .",
        "",
        f"<{uri}>",
        f'    a prov:Entity ;',
        f'    prov:wasGeneratedBy <{activity_uri}> ;',
        f'    prov:wasAttributedTo <{agent_uri}> ;',
        f'    prov:generatedAtTime "{ts}"^^xsd:dateTime ;',
        f'    dq:vendorId "{vendor}"^^xsd:string ;',
        f'    dq:hasQualityScore "{q}"^^xsd:decimal .',
        "",
        f"<{activity_uri}>",
        f'    a prov:Activity ;',
        f'    prov:startedAtTime "{ts}"^^xsd:dateTime ;',
        f'    prov:wasAssociatedWith <{agent_uri}> .',
        "",
        f"<{agent_uri}>",
        f'    a prov:Agent ;',
        f'    prov:actedOnBehalfOf <http://example.org/agent/AgriSem> .',
    ]
    return "\n".join(lines)
