"""
evaluation/run_experiments.py
Orchestrateur 840+ runs avec IC 95%.
"""

import os
import csv
import time
import logging
import yaml
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

RESULTS_DIR = "results"


def load_experiment_config() -> dict:
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "experiment_config.yaml"
    )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_single_experiment(
    n_observations: int,
    anomaly_rate: float,
    vendor_filter: str,
    mode: str,
    seed: int,
) -> dict:
    """Exécute un seul run expérimental."""
    from generator.payload_generator import generate_batch
    from generator.anomaly_injector import inject_batch
    from pipeline.vendor_router import route
    from pipeline.normalizer import normalize
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation
    from evaluation.metrics import aggregate_metrics

    # Générer les données
    nodes = None
    if vendor_filter != "mixed":
        vendor_node = {"A": "node_2", "B": "node_3", "C": "node_4", "D": "node_5"}
        nodes = [vendor_node.get(vendor_filter, "node_2")]

    readings = generate_batch(n=n_observations, nodes=nodes, seed=seed)

    # Injecter des anomalies
    readings_with_anomalies, anomaly_indices = inject_batch(
        readings, anomaly_rate=anomaly_rate, seed=seed
    )

    t0 = time.perf_counter()
    processed = []

    for obs in readings_with_anomalies:
        try:
            routed = route(obs)
            normalized = normalize(routed)

            if mode == "ablation_no_shacl":
                normalized["_f4_plausibility"] = 1.0
                repaired = repair(normalized)
                scored = score_observation(repaired)
            elif mode == "ablation_no_unitnorm":
                normalized["_unit_confidence"] = 0.5
                report, f1, f4 = validate(normalized)
                normalized["_f4_plausibility"] = f4
                normalized["_completeness"] = f1
                repaired = repair(normalized)
                scored = score_observation(repaired)
            elif mode == "ablation_no_quality":
                report, f1, f4 = validate(normalized)
                normalized["_f4_plausibility"] = f4
                normalized["_completeness"] = f1
                repaired = repair(normalized)
                repaired["_Q"] = 1.0
                scored = repaired
            elif mode == "ablation_no_repair":
                report, f1, f4 = validate(normalized)
                normalized["_f4_plausibility"] = f4
                normalized["_completeness"] = f1
                normalized["_repairs"] = []
                normalized["_repaired"] = False
                scored = score_observation(normalized)
            else:  # full
                report, f1, f4 = validate(normalized)
                normalized["_f4_plausibility"] = f4
                normalized["_completeness"] = f1
                repaired = repair(normalized, report)
                scored = score_observation(repaired)

            processed.append(scored)
        except Exception as exc:
            logger.warning("Erreur processing : %s", exc)

    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000

    from evaluation.metrics import (
        compute_qsr, compute_f1_anomaly, compute_repair_rate
    )
    qsr = compute_qsr(processed)
    f1_metric = compute_f1_anomaly(processed, anomaly_indices)
    repair_metric = compute_repair_rate(processed)

    return {
        "n_observations": n_observations,
        "anomaly_rate": anomaly_rate,
        "vendor": vendor_filter,
        "mode": mode,
        "seed": seed,
        "qsr_mean": qsr["mean"],
        "qsr_std": qsr["std"],
        "qsr_ci95": qsr["ci_95"],
        "f1_anomaly": f1_metric["f1"],
        "precision": f1_metric["precision"],
        "recall": f1_metric["recall"],
        "repair_rate": repair_metric["repair_rate"],
        "latency_total_ms": round(latency_ms, 2),
        "latency_per_obs_ms": round(latency_ms / max(n_observations, 1), 4),
        "throughput_obs_s": round(n_observations / max((t1 - t0), 1e-9), 2),
        "n_processed": len(processed),
    }


def run_experiments(
    config: dict | None = None,
    max_runs: int | None = None,
    output_csv: str = "results/experiment_results.csv",
) -> list[dict]:
    """
    Orchestre tous les runs expérimentaux.
    """
    if config is None:
        config = load_experiment_config()

    params = config.get("parameters", {})
    n_obs_list = params.get("n_observations", [100])
    anomaly_rates = params.get("anomaly_rates", [0.10])
    vendors = params.get("vendors", ["mixed"])
    modes = params.get("pipeline_modes", ["full"])
    seeds = config.get("experiment", {}).get("random_seeds", [42])

    os.makedirs(RESULTS_DIR, exist_ok=True)

    all_results = []
    run_count = 0

    for n_obs in n_obs_list:
        for anom_rate in anomaly_rates:
            for vendor in vendors:
                for mode in modes:
                    for seed in seeds:
                        if max_runs and run_count >= max_runs:
                            break
                        logger.info(
                            "Run %d: n=%d, anom=%.2f, vendor=%s, mode=%s, seed=%d",
                            run_count, n_obs, anom_rate, vendor, mode, seed
                        )
                        try:
                            result = run_single_experiment(
                                n_observations=n_obs,
                                anomaly_rate=anom_rate,
                                vendor_filter=vendor,
                                mode=mode,
                                seed=seed,
                            )
                            all_results.append(result)
                        except Exception as exc:
                            logger.error("Run %d échoué : %s", run_count, exc)
                        run_count += 1

    # Sauvegarder les résultats
    if all_results:
        _save_results(all_results, output_csv)

    logger.info("Expériences terminées : %d runs", len(all_results))
    return all_results


def _save_results(results: list[dict], filepath: str):
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    if not results:
        return
    fields = list(results[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    logger.info("Résultats sauvegardés : %s", filepath)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_experiments(max_runs=50)
    print(f"Expériences terminées : {len(results)} runs")
