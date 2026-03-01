"""
pipeline/cooja_bridge.py
Parse les données brutes Cooja et fetch HTTP depuis les nœuds IPv6.
"""

import re
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Adresses IPv6 des nœuds Cooja (du repo daksh-patel-nitw/Smart-Farming-IOT)
COOJA_NODES = {
    "node_2": "http://[aaaa::212:7402:2:202]",
    "node_3": "http://[aaaa::212:7403:3:303]",
    "node_4": "http://[aaaa::212:7404:4:404]",
    "node_5": "http://[aaaa::212:7405:5:505]",
    "node_6": "http://[aaaa::212:7406:6:606]",
}

# Mapping clés Cooja → noms standards
COOJA_KEY_MAP = {
    "ph":   "ph",
    "Temp": "temperature",
    "turb": "turbidity",
    "am":   "ammonia",
    "ox":   "oxygen",
    "mo":   "moisture",
    "hu":   "humidity",
}

# Mapping nœud → vendor
NODE_VENDOR_MAP = {
    "node_2": "A",
    "node_3": "B",
    "node_4": "C",
    "node_5": "D",
    "node_6": "A",
}


def parse_cooja_string(raw: str) -> dict:
    """
    Parse la chaîne Cooja : "ph:7 Temp:25 turb:30 am:5 ox:8 mo:35 hu:55"
    Retourne un dict avec les clés standards.
    """
    result = {}
    pairs = raw.strip().split()
    for pair in pairs:
        if ":" in pair:
            key, value = pair.split(":", 1)
            key = key.strip()
            std_key = COOJA_KEY_MAP.get(key, key.lower())
            try:
                result[std_key] = float(value.strip())
            except ValueError:
                result[std_key] = value.strip()
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


def fetch_node(node_id: str, timeout: float = 5.0) -> dict | None:
    """
    Fetch les données HTTP depuis un nœud Cooja.
    Retourne le dict parsé ou None en cas d'erreur.
    """
    url = COOJA_NODES.get(node_id)
    if not url:
        logger.error("Nœud inconnu : %s", node_id)
        return None
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = parse_cooja_string(resp.text)
        data["node_id"] = node_id
        data["vendor"] = NODE_VENDOR_MAP.get(node_id, "A")
        return data
    except requests.RequestException as exc:
        logger.warning("Erreur fetch nœud %s : %s", node_id, exc)
        return None


def fetch_all_nodes(timeout: float = 5.0) -> list[dict]:
    """
    Fetch toutes les données depuis les nœuds Cooja disponibles.
    """
    results = []
    for node_id in COOJA_NODES:
        data = fetch_node(node_id, timeout=timeout)
        if data is not None:
            results.append(data)
    return results


def get_synthetic_reading(node_id: str = "node_2") -> dict:
    """
    Génère une lecture synthétique simulant un nœud Cooja.
    Utilisé en mode STANDALONE.
    """
    raw = "ph:7 Temp:25 turb:30 am:5 ox:8 mo:35 hu:55"
    data = parse_cooja_string(raw)
    data["node_id"] = node_id
    data["vendor"] = NODE_VENDOR_MAP.get(node_id, "A")
    return data
