"""
server.py — Point d'entrée principal AgriSem Framework
Port : 12345
Modes : LIVE (Cooja) et STANDALONE (données synthétiques)

Endpoints :
  GET  /              → Pipeline complet (une observation par nœud)
  GET  /metrics       → Métriques agrégées
  GET  /health        → Health check
  POST /sendAccutatorSignal → Décision actionneurs
"""

import os
import sys
import time
import logging
import json
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Configuration ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

MODE = os.environ.get("AGRISEM_MODE", "standalone").lower()
PORT = int(os.environ.get("AGRISEM_PORT", 12345))

app = Flask(__name__)
CORS(app)

# ── Historique des observations (fenêtre glissante) ───────────────────────────
_observation_history: list[dict] = []
MAX_HISTORY = 500

# ── Métriques globales ─────────────────────────────────────────────────────────
_global_metrics = {
    "total_requests": 0,
    "total_observations": 0,
    "errors": 0,
    "start_time": datetime.now(timezone.utc).isoformat(),
}


def run_pipeline_standalone() -> list[dict]:
    """Exécute le pipeline en mode STANDALONE avec données synthétiques."""
    from generator.payload_generator import generate_batch
    from generator.anomaly_injector import inject_batch
    from pipeline.vendor_router import route
    from pipeline.normalizer import normalize
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation
    from pipeline.provenance import create_provenance
    from pipeline.kg_manager import insert_observation, is_fuseki_available

    # Générer des données synthétiques (5 nœuds)
    nodes = ["node_2", "node_3", "node_4", "node_5", "node_6"]
    readings = generate_batch(n=len(nodes), nodes=nodes)

    # Injecter des anomalies aléatoires (15% de taux)
    readings_with_anomalies, _ = inject_batch(readings, anomaly_rate=0.15)

    results = []
    for raw_obs in readings_with_anomalies:
        try:
            t_start = time.perf_counter()

            # Étape 1 : Parse Cooja (déjà parsé en mode standalone)
            # Étape 2 : Vendor routing
            routed = route(raw_obs)

            # Étape 3 : Normalisation
            normalized = normalize(routed)

            # Étape 4 : Validation SHACL
            report, f1, f4 = validate(normalized)
            normalized["_validation"] = report.to_dict()
            normalized["_f4_plausibility"] = f4
            normalized["_completeness"] = f1

            # Étape 5 : Réparation
            repaired = repair(normalized, report)

            # Étape 6 : Quality Scoring
            scored = score_observation(repaired)

            # Étape 7 : Insert KG (si Fuseki disponible)
            kg_inserted = False
            if is_fuseki_available():
                kg_inserted = insert_observation(scored)

            # Étape 8 : Provenance
            prov = create_provenance(scored)

            t_end = time.perf_counter()
            latency_ms = (t_end - t_start) * 1000

            # Résultat final
            result = {
                "node_id": scored.get("sensor_id", raw_obs.get("node_id")),
                "vendor": scored.get("_vendor"),
                "timestamp": scored.get("timestamp"),
                "measurements": {
                    "temperature": scored.get("temperature"),
                    "humidity":    scored.get("humidity"),
                    "moisture":    scored.get("moisture"),
                    "ph":          scored.get("ph"),
                    "oxygen":      scored.get("oxygen"),
                    "ammonia":     scored.get("ammonia"),
                    "turbidity":   scored.get("turbidity"),
                },
                "quality": scored.get("_quality_score", {}),
                "Q": scored.get("_Q", 0.0),
                "validation": report.to_dict(),
                "repairs": scored.get("_repairs", []),
                "flags": scored.get("_flags", []),
                "conversions": scored.get("_conversions", []),
                "provenance_id": prov.get("id"),
                "kg_inserted": kg_inserted,
                "latency_ms": round(latency_ms, 2),
            }
            results.append(result)

        except Exception as exc:
            logger.error("Erreur pipeline pour nœud %s : %s",
                         raw_obs.get("node_id", "?"), exc)
            _global_metrics["errors"] += 1

    return results


def run_pipeline_live() -> list[dict]:
    """Exécute le pipeline en mode LIVE avec les nœuds Cooja."""
    from pipeline.cooja_bridge import fetch_all_nodes
    from pipeline.vendor_router import route
    from pipeline.normalizer import normalize
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation
    from pipeline.provenance import create_provenance
    from pipeline.kg_manager import insert_observation, is_fuseki_available

    raw_readings = fetch_all_nodes(timeout=5.0)

    if not raw_readings:
        logger.warning("Aucun nœud Cooja accessible — basculement en mode STANDALONE")
        return run_pipeline_standalone()

    results = []
    for raw_obs in raw_readings:
        try:
            t_start = time.perf_counter()
            routed = route(raw_obs)
            normalized = normalize(routed)
            report, f1, f4 = validate(normalized)
            normalized["_validation"] = report.to_dict()
            normalized["_f4_plausibility"] = f4
            normalized["_completeness"] = f1
            repaired = repair(normalized, report)
            scored = score_observation(repaired)

            kg_inserted = False
            if is_fuseki_available():
                kg_inserted = insert_observation(scored)

            prov = create_provenance(scored)
            t_end = time.perf_counter()

            result = {
                "node_id": scored.get("sensor_id", raw_obs.get("node_id")),
                "vendor": scored.get("_vendor"),
                "timestamp": scored.get("timestamp"),
                "measurements": {
                    "temperature": scored.get("temperature"),
                    "humidity":    scored.get("humidity"),
                    "moisture":    scored.get("moisture"),
                    "ph":          scored.get("ph"),
                    "oxygen":      scored.get("oxygen"),
                    "ammonia":     scored.get("ammonia"),
                    "turbidity":   scored.get("turbidity"),
                },
                "quality": scored.get("_quality_score", {}),
                "Q": scored.get("_Q", 0.0),
                "validation": report.to_dict(),
                "repairs": scored.get("_repairs", []),
                "flags": scored.get("_flags", []),
                "conversions": scored.get("_conversions", []),
                "provenance_id": prov.get("id"),
                "kg_inserted": kg_inserted,
                "latency_ms": round((t_end - t_start) * 1000, 2),
            }
            results.append(result)

        except Exception as exc:
            logger.error("Erreur pipeline nœud %s : %s",
                         raw_obs.get("node_id", "?"), exc)
            _global_metrics["errors"] += 1

    return results


# ── Endpoints Flask ────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def pipeline_endpoint():
    """Pipeline complet : collecte → sémantique → KG → décision."""
    global _observation_history, _global_metrics

    t0 = time.perf_counter()
    _global_metrics["total_requests"] += 1

    try:
        if MODE == "live":
            observations = run_pipeline_live()
        else:
            observations = run_pipeline_standalone()

        # Stocker dans l'historique
        _observation_history.extend(observations)
        if len(_observation_history) > MAX_HISTORY:
            _observation_history = _observation_history[-MAX_HISTORY:]

        _global_metrics["total_observations"] += len(observations)

        # Décision quality-aware
        from pipeline.reasoner import decide
        decision = decide(observations)

        total_ms = (time.perf_counter() - t0) * 1000
        avg_q = sum(o.get("Q", 0) for o in observations) / max(len(observations), 1)

        return jsonify({
            "status": "ok",
            "mode": MODE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_observations": len(observations),
            "average_Q": round(avg_q, 4),
            "observations": observations,
            "decision": decision,
            "pipeline_ms": round(total_ms, 2),
        })

    except Exception as exc:
        logger.exception("Erreur endpoint / : %s", exc)
        _global_metrics["errors"] += 1
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/metrics", methods=["GET"])
def metrics_endpoint():
    """Métriques agrégées du pipeline."""
    from evaluation.metrics import compute_qsr, compute_f1_anomaly, compute_repair_rate

    history = _observation_history.copy()

    qsr = compute_qsr(history)
    f1_metric = compute_f1_anomaly(history)
    repair_metric = compute_repair_rate(history)

    from pipeline.reasoner import decide
    decision = decide(history) if history else {}

    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": MODE,
        "global": _global_metrics,
        "qsr": qsr,
        "f1_anomaly": f1_metric,
        "repair": repair_metric,
        "decision": decision,
        "history_size": len(history),
    })


@app.route("/health", methods=["GET"])
def health_endpoint():
    """Health check."""
    from pipeline.kg_manager import is_fuseki_available

    fuseki_ok = is_fuseki_available()

    return jsonify({
        "status": "ok",
        "mode": MODE,
        "fuseki": fuseki_ok,
        "uptime_s": round(
            (datetime.now(timezone.utc) -
             datetime.fromisoformat(_global_metrics["start_time"])).total_seconds(), 1
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/sendAccutatorSignal", methods=["POST"])
def actuator_signal_endpoint():
    """Décision actionneurs quality-aware."""
    from pipeline.reasoner import decide

    body = request.get_json(silent=True) or {}

    # Utiliser les observations récentes ou celles fournies
    observations = body.get("observations") or _observation_history[-50:]

    if not observations:
        if MODE == "live":
            observations = run_pipeline_live()
        else:
            observations = run_pipeline_standalone()

    decision = decide(observations)
    triggered = decision.get("actions", [])

    response = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "triggered_actions": triggered,
        "n_observations_used": len(observations),
        "average_Q": round(
            sum(o.get("Q", o.get("_Q", 0)) for o in observations) / max(len(observations), 1),
            4
        ),
    }

    logger.info("Actuator signal : %s (Confiance=%.3f)",
                triggered or "none", decision.get("confidence", 0))

    return jsonify(response)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("AgriSem Framework — Démarrage (mode=%s, port=%d)", MODE, PORT)
    logger.info("Endpoints :")
    logger.info("  GET  http://localhost:%d/", PORT)
    logger.info("  GET  http://localhost:%d/metrics", PORT)
    logger.info("  GET  http://localhost:%d/health", PORT)
    logger.info("  POST http://localhost:%d/sendAccutatorSignal", PORT)

    app.run(host="0.0.0.0", port=PORT, debug=False)
