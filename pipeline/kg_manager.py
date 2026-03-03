"""
pipeline/kg_manager.py
Knowledge Graph manager with in-memory rdflib Graph and optional Fuseki SPARQL.
Supports SOSA/SSN-compliant RDF observations with quality score materialization.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from rdflib import Graph, Namespace, URIRef, Literal, ConjunctiveGraph
    from rdflib.namespace import RDF, XSD, OWL
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    logger.warning("rdflib not available — in-memory KG disabled")

try:
    from SPARQLWrapper import SPARQLWrapper, JSON, POST, GET
    SPARQL_AVAILABLE = True
except ImportError:
    SPARQL_AVAILABLE = False
    logger.warning("SPARQLWrapper not available — Fuseki KG disabled")

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Namespaces
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSN = Namespace("http://www.w3.org/ns/ssn/")
DQ = Namespace("http://example.org/dq#")
AGRI = Namespace("http://example.org/agri#")
EX = Namespace("http://example.org/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
PROV = Namespace("http://www.w3.org/ns/prov#")

FUSEKI_BASE_URL = os.environ.get("FUSEKI_URL", "http://localhost:3030")
DATASET = "agrisem"
FUSEKI_AUTH = ("admin", "admin")

# SPARQL Prefixes
PREFIXES = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dq:   <http://example.org/dq#>
PREFIX agri: <http://example.org/agri#>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX unit: <http://qudt.org/vocab/unit/>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""

# In-memory KG (rdflib Graph)
_in_memory_graph: Optional[Graph] = None


def get_in_memory_graph() -> Optional[Graph]:
    """Get or create the in-memory rdflib Graph."""
    global _in_memory_graph
    if not RDFLIB_AVAILABLE:
        return None
    if _in_memory_graph is None:
        _in_memory_graph = Graph()
        _in_memory_graph.bind("sosa", SOSA)
        _in_memory_graph.bind("dq", DQ)
        _in_memory_graph.bind("agri", AGRI)
        _in_memory_graph.bind("qudt", QUDT)
        _in_memory_graph.bind("unit", UNIT)
        _in_memory_graph.bind("prov", PROV)
    return _in_memory_graph


def reset_in_memory_graph() -> None:
    """Reset the in-memory graph (for testing)."""
    global _in_memory_graph
    _in_memory_graph = None


def observation_to_rdf_graph(observation: dict) -> "Optional[tuple]":
    """
    Convert a normalized observation dict to an rdflib Graph with SOSA/SSN triples.
    
    Produces triples in the format:
        ex:obs-XXX a sosa:Observation ;
            sosa:observedProperty ex:SoilMoisture ;
            sosa:madeBySensor ex:sensor-XXX ;
            sosa:hasFeatureOfInterest agri:Plot_P1 ;
            sosa:resultTime "2026-02-28T10:15:00Z"^^xsd:dateTime ;
            sosa:hasResult ex:res-XXX ;
            dq:qualityScore "0.82"^^xsd:decimal ;
            dq:unitConfidence "1.0"^^xsd:decimal ;
            dq:anomalyFlag false .
        ex:res-XXX a qudt:QuantityValue ;
            qudt:numericValue "23.4"^^xsd:decimal ;
            qudt:unit unit:PERCENT .
    """
    if not RDFLIB_AVAILABLE:
        return None

    g = Graph()
    g.bind("sosa", SOSA)
    g.bind("dq", DQ)
    g.bind("agri", AGRI)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("prov", PROV)

    obs_id = str(uuid.uuid4())[:8]
    sensor_id = observation.get("sensor_id", "unknown")
    obs_uri = EX[f"obs-{sensor_id}-{obs_id}"]
    res_uri = EX[f"res-{sensor_id}-{obs_id}"]
    sensor_uri = EX[f"sensor-{sensor_id}"]
    plot_id = observation.get("_plot", "P1")
    plot_uri = AGRI[f"Plot_{plot_id}"]

    # Core SOSA triples
    g.add((obs_uri, RDF.type, SOSA.Observation))
    g.add((obs_uri, SOSA.madeBySensor, sensor_uri))
    g.add((obs_uri, SOSA.hasFeatureOfInterest, plot_uri))
    g.add((obs_uri, SOSA.hasResult, res_uri))
    g.add((res_uri, RDF.type, QUDT.QuantityValue))

    # Observed property
    moisture = observation.get("moisture", observation.get("soilMoisture"))
    if moisture is not None:
        g.add((obs_uri, SOSA.observedProperty, AGRI.SoilMoisture))
        g.add((res_uri, QUDT.numericValue, Literal(float(moisture), datatype=XSD.decimal)))
        g.add((res_uri, QUDT.unit, UNIT.PERCENT))

    # Timestamp
    ts = observation.get("timestamp", datetime.now(timezone.utc).isoformat())
    ts_str = str(ts).replace("Z", "+00:00")
    try:
        datetime.fromisoformat(ts_str)
        g.add((obs_uri, SOSA.resultTime, Literal(ts_str, datatype=XSD.dateTime)))
    except ValueError:
        now = datetime.now(timezone.utc).isoformat()
        g.add((obs_uri, SOSA.resultTime, Literal(now, datatype=XSD.dateTime)))

    # Vendor
    vendor = observation.get("_vendor", "A")
    g.add((obs_uri, DQ.vendorId, Literal(str(vendor), datatype=XSD.string)))

    # Quality score materialized as RDF triples
    q_score = observation.get("_Q", 0.0)
    g.add((obs_uri, DQ.qualityScore, Literal(float(q_score), datatype=XSD.decimal)))

    qs = observation.get("_quality_score", {})
    if qs:
        f2 = qs.get("f2_unit_confidence", observation.get("_unit_confidence", 1.0))
        g.add((obs_uri, DQ.unitConfidence, Literal(float(f2), datatype=XSD.decimal)))
        for fi, pred in [
            ("f1_completeness",    DQ.completeness),
            ("f2_unit_confidence", DQ.unitConfidence),
            ("f3_freshness",       DQ.freshness),
            ("f4_plausibility",    DQ.plausibility),
            ("f5_reliability",     DQ.reliability),
        ]:
            v = qs.get(fi)
            if v is not None:
                g.add((obs_uri, pred, Literal(float(v), datatype=XSD.decimal)))

    # Anomaly flag
    has_anomaly = bool(observation.get("_has_anomaly") or observation.get("_flags"))
    g.add((obs_uri, DQ.anomalyFlag, Literal(has_anomaly, datatype=XSD.boolean)))

    # Measurement fields as dq: properties
    field_map = {
        "temperature":   DQ.airTemperature,
        "humidity":      DQ.humidity,
        "moisture":      DQ.soilMoisture,
        "ph":            DQ.soilPH,
        "oxygen":        DQ.oxygen,
        "ammonia":       DQ.ammonia,
        "turbidity":     DQ.turbidity,
        "soilMoisture":  DQ.soilMoisture,
        "airTemperature": DQ.airTemperature,
        "soilPH":        DQ.soilPH,
        "batteryLevel":  DQ.batteryLevel,
    }
    for field, pred in field_map.items():
        val = observation.get(field)
        if val is not None:
            try:
                g.add((obs_uri, pred, Literal(float(val), datatype=XSD.decimal)))
            except (TypeError, ValueError):
                pass

    return g, obs_uri


def add_observation_to_memory(observation: dict) -> bool:
    """Add an observation to the in-memory rdflib Graph."""
    if not RDFLIB_AVAILABLE:
        return False
    kg = get_in_memory_graph()
    if kg is None:
        return False
    try:
        result = observation_to_rdf_graph(observation)
        if result is None:
            return False
        obs_graph, _ = result
        for triple in obs_graph:
            kg.add(triple)
        return True
    except Exception as exc:
        logger.warning("Error adding to in-memory KG: %s", exc)
        return False


def query_in_memory(sparql_query: str) -> list:
    """Execute a SPARQL SELECT query against the in-memory graph."""
    if not RDFLIB_AVAILABLE:
        return []
    kg = get_in_memory_graph()
    if kg is None:
        return []
    try:
        results = kg.query(PREFIXES + "\n" + sparql_query)
        rows = []
        for row in results:
            rows.append({str(var): str(row[var]) for var in results.vars if row[var] is not None})
        return rows
    except Exception as exc:
        logger.warning("In-memory SPARQL query error: %s", exc)
        return []


def get_in_memory_triple_count() -> int:
    """Get number of triples in the in-memory graph."""
    if not RDFLIB_AVAILABLE:
        return 0
    kg = get_in_memory_graph()
    return len(kg) if kg else 0


def is_fuseki_available() -> bool:
    """Check if Fuseki is accessible."""
    if not REQUESTS_AVAILABLE:
        return False
    try:
        resp = _requests.get(f"{FUSEKI_BASE_URL}/$/ping", timeout=3, auth=FUSEKI_AUTH)
        return resp.status_code == 200
    except Exception:
        return False


def create_dataset(dataset: str = DATASET) -> bool:
    """Create dataset in Fuseki if it doesn't exist."""
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
        logger.warning("Dataset creation error: %s", exc)
        return False


def observation_to_sparql_update(observation: dict) -> str:
    """Generate SPARQL UPDATE to insert an observation into the KG."""
    obs_id = str(uuid.uuid4())
    obs_uri = f"http://example.org/obs/{obs_id}"
    sensor_id = observation.get("sensor_id", "unknown")
    sensor_uri = f"http://example.org/sensor/{sensor_id}"
    vendor = observation.get("_vendor", "A")
    ts = observation.get("timestamp", datetime.now(timezone.utc).isoformat())
    q_score = observation.get("_Q", 0.0)
    plot_id = observation.get("_plot", "P1")

    triples = []
    triples.append(f"<{obs_uri}> rdf:type sosa:Observation .")
    triples.append(f"<{obs_uri}> sosa:madeBySensor <{sensor_uri}> .")
    triples.append(f'<{obs_uri}> sosa:resultTime "{ts}"^^xsd:dateTime .')
    triples.append(f'<{obs_uri}> sosa:hasFeatureOfInterest agri:Plot_{plot_id} .')
    triples.append(f'<{obs_uri}> dq:vendorId "{vendor}"^^xsd:string .')
    triples.append(f'<{obs_uri}> dq:qualityScore "{q_score}"^^xsd:decimal .')
    triples.append(f'<{obs_uri}> dq:anomalyFlag "{bool(observation.get("_has_anomaly"))}"^^xsd:boolean .')

    # Measurement fields
    field_map = {
        "temperature":   "dq:airTemperature",
        "humidity":      "dq:humidity",
        "moisture":      "dq:soilMoisture",
        "ph":            "dq:soilPH",
        "oxygen":        "dq:oxygen",
        "ammonia":       "dq:ammonia",
        "turbidity":     "dq:turbidity",
        "batteryLevel":  "dq:batteryLevel",
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
    """Insert an observation into Fuseki via SPARQL UPDATE."""
    if not SPARQL_AVAILABLE:
        logger.debug("SPARQLWrapper unavailable — insert skipped")
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
        logger.warning("KG insert error: %s", exc)
        return False


def add_observation(observation: dict, dataset: str = DATASET) -> bool:
    """
    Add observation to both in-memory graph and Fuseki (if available).
    Always succeeds if in-memory is available.
    """
    # Always add to in-memory graph
    in_mem_ok = add_observation_to_memory(observation)
    # Also try Fuseki if available
    if SPARQL_AVAILABLE and is_fuseki_available():
        insert_observation(observation, dataset)
    return in_mem_ok


def query_observations(dataset: str = DATASET, limit: int = 10) -> list:
    """Query observations from KG (in-memory first, then Fuseki)."""
    sparql_query = f"""
SELECT ?obs ?sensor ?ts ?Q ?vendor WHERE {{
    ?obs rdf:type sosa:Observation ;
         sosa:madeBySensor ?sensor ;
         sosa:resultTime ?ts ;
         dq:qualityScore ?Q ;
         dq:vendorId ?vendor .
}}
ORDER BY DESC(?ts)
LIMIT {limit}
"""
    # Try in-memory first
    if RDFLIB_AVAILABLE:
        results = query_in_memory(sparql_query)
        if results:
            return results

    # Fall back to Fuseki
    if not SPARQL_AVAILABLE or not is_fuseki_available():
        return []

    try:
        sparql = SPARQLWrapper(f"{FUSEKI_BASE_URL}/{dataset}/query")
        sparql.setQuery(PREFIXES + sparql_query)
        sparql.setReturnFormat(JSON)
        sparql.setCredentials(*FUSEKI_AUTH)
        results = sparql.query().convert()
        rows = []
        for binding in results["results"]["bindings"]:
            rows.append({k: v["value"] for k, v in binding.items()})
        return rows
    except Exception as exc:
        logger.warning("KG query error: %s", exc)
        return []


def count_observations(dataset: str = DATASET) -> int:
    """Return number of observations in the KG."""
    # Try in-memory
    if RDFLIB_AVAILABLE:
        kg = get_in_memory_graph()
        if kg:
            count_query = "SELECT (COUNT(?obs) AS ?count) WHERE { ?obs rdf:type sosa:Observation . }"
            try:
                results = list(kg.query(PREFIXES + "\n" + count_query))
                if results:
                    return int(str(results[0][0]))
            except Exception:
                pass

    # Fall back to Fuseki
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
