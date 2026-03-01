"""
pipeline/kg_manager.py
Gestion du Knowledge Graph Apache Jena Fuseki.
Insert SPARQL UPDATE, requêtes SPARQL, création dataset.
"""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from SPARQLWrapper import SPARQLWrapper, JSON, POST, GET
    SPARQL_AVAILABLE = True
except ImportError:
    SPARQL_AVAILABLE = False
    logger.warning("SPARQLWrapper non disponible — KG désactivé")

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


FUSEKI_BASE_URL = "http://localhost:3030"
DATASET = "agrisem"
FUSEKI_AUTH = ("admin", "admin")

# Préfixes SPARQL
PREFIXES = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dq:   <http://example.org/dq#>
PREFIX agri: <http://example.org/agri#>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""


def is_fuseki_available() -> bool:
    """Vérifie si Fuseki est accessible."""
    if not REQUESTS_AVAILABLE:
        return False
    try:
        resp = _requests.get(f"{FUSEKI_BASE_URL}/$/ping", timeout=3, auth=FUSEKI_AUTH)
        return resp.status_code == 200
    except Exception:
        return False


def create_dataset(dataset: str = DATASET) -> bool:
    """Crée le dataset dans Fuseki si inexistant."""
    if not REQUESTS_AVAILABLE:
        return False
    try:
        resp = _requests.post(
            f"{FUSEKI_BASE_URL}/$/datasets",
            auth=FUSEKI_AUTH,
            data={"dbName": dataset, "dbType": "tdb2"},
            timeout=10,
        )
        return resp.status_code in (200, 201, 409)
    except Exception as exc:
        logger.warning("Erreur création dataset : %s", exc)
        return False


def observation_to_sparql_update(observation: dict) -> str:
    """
    Génère un SPARQL UPDATE pour insérer une observation dans le KG.
    """
    obs_id = str(uuid.uuid4())
    obs_uri = f"http://example.org/obs/{obs_id}"
    sensor_id = observation.get("sensor_id", "unknown")
    sensor_uri = f"http://example.org/sensor/{sensor_id}"
    vendor = observation.get("_vendor", "A")
    ts = observation.get("timestamp", datetime.now(timezone.utc).isoformat())
    q_score = observation.get("_Q", 0.0)

    triples = []
    triples.append(f"<{obs_uri}> rdf:type sosa:Observation .")
    triples.append(f'<{obs_uri}> sosa:madeBySensor <{sensor_uri}> .')
    triples.append(f'<{obs_uri}> sosa:resultTime "{ts}"^^xsd:dateTime .')
    triples.append(f'<{obs_uri}> dq:vendorId "{vendor}"^^xsd:string .')
    triples.append(f'<{obs_uri}> dq:hasQualityScore "{q_score}"^^xsd:decimal .')

    # Mesures
    field_map = {
        "temperature": "dq:temperature",
        "humidity":    "dq:humidity",
        "moisture":    "dq:moisture",
        "ph":          "dq:ph",
        "oxygen":      "dq:oxygen",
        "ammonia":     "dq:ammonia",
        "turbidity":   "dq:turbidity",
    }
    for field, predicate in field_map.items():
        val = observation.get(field)
        if val is not None:
            triples.append(f'<{obs_uri}> {predicate} "{float(val)}"^^xsd:decimal .')

    # Quality factors
    qs = observation.get("_quality_score", {})
    for fi, pred in [
        ("f1_completeness",    "dq:completeness"),
        ("f2_unit_confidence", "dq:unitConfidence"),
        ("f3_freshness",       "dq:freshness"),
        ("f4_plausibility",    "dq:plausibility"),
        ("f5_reliability",     "dq:reliability"),
    ]:
        v = qs.get(fi)
        if v is not None:
            triples.append(f'<{obs_uri}> {pred} "{float(v)}"^^xsd:decimal .')

    triples_str = "\n    ".join(triples)
    return f"{PREFIXES}\nINSERT DATA {{\n    {triples_str}\n}}"


def insert_observation(observation: dict, dataset: str = DATASET) -> bool:
    """
    Insère une observation dans Fuseki via SPARQL UPDATE.
    """
    if not SPARQL_AVAILABLE:
        logger.debug("SPARQLWrapper indisponible — insert ignoré")
        return False

    query = observation_to_sparql_update(observation)
    try:
        sparql = SPARQLWrapper(f"{FUSEKI_BASE_URL}/{dataset}/update")
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.setCredentials(*FUSEKI_AUTH)
        sparql.query()
        return True
    except Exception as exc:
        logger.warning("Erreur insert KG : %s", exc)
        return False


def query_observations(
    dataset: str = DATASET,
    limit: int = 10,
) -> list[dict]:
    """
    Requête SPARQL pour récupérer les dernières observations.
    """
    if not SPARQL_AVAILABLE or not is_fuseki_available():
        return []

    sparql_query = f"""
{PREFIXES}
SELECT ?obs ?sensor ?ts ?Q ?vendor WHERE {{
    ?obs rdf:type sosa:Observation ;
         sosa:madeBySensor ?sensor ;
         sosa:resultTime ?ts ;
         dq:hasQualityScore ?Q ;
         dq:vendorId ?vendor .
}}
ORDER BY DESC(?ts)
LIMIT {limit}
"""
    try:
        sparql = SPARQLWrapper(f"{FUSEKI_BASE_URL}/{dataset}/query")
        sparql.setQuery(sparql_query)
        sparql.setReturnFormat(JSON)
        sparql.setCredentials(*FUSEKI_AUTH)
        results = sparql.query().convert()
        rows = []
        for binding in results["results"]["bindings"]:
            rows.append({k: v["value"] for k, v in binding.items()})
        return rows
    except Exception as exc:
        logger.warning("Erreur requête KG : %s", exc)
        return []


def count_observations(dataset: str = DATASET) -> int:
    """Retourne le nombre d'observations dans le KG."""
    if not SPARQL_AVAILABLE or not is_fuseki_available():
        return 0

    query = f"""
{PREFIXES}
SELECT (COUNT(?obs) AS ?count) WHERE {{
    ?obs rdf:type sosa:Observation .
}}
"""
    try:
        sparql = SPARQLWrapper(f"{FUSEKI_BASE_URL}/{dataset}/query")
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        sparql.setCredentials(*FUSEKI_AUTH)
        results = sparql.query().convert()
        bindings = results["results"]["bindings"]
        if bindings:
            return int(bindings[0]["count"]["value"])
    except Exception:
        pass
    return 0
