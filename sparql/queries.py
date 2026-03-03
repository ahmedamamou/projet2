"""
sparql/queries.py
10 standardized SPARQL queries for the agricultural Knowledge Graph (QSR).
Implements compute_qsr() that runs all 10 queries and returns QSR = correct / 10.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

PREFIXES = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dq:   <http://example.org/dq#>
PREFIX agri: <http://example.org/agri#>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX unit: <http://qudt.org/vocab/unit/>
"""

# Q1: Latest soil moisture per plot
Q1_LATEST_SOIL_MOISTURE = """
SELECT ?plot (MAX(?ts) AS ?latest_ts) ?moisture WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:soilMoisture ?moisture .
}
GROUP BY ?plot ?moisture
ORDER BY DESC(?latest_ts)
"""

# Q2: Average moisture (last hour) for a plot
# Note: FILTER with NOW() uses query execution time. For simulated/historical data with
# fixed timestamps, all observations may be excluded. Use Q1 for historical analysis.
Q2_AVG_MOISTURE_LAST_HOUR = """
SELECT ?plot (AVG(?moisture) AS ?avg_moisture) (COUNT(?obs) AS ?n) WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:soilMoisture ?moisture .
    FILTER (?ts >= NOW() - "PT1H"^^xsd:duration)
}
GROUP BY ?plot
ORDER BY ?plot
"""

# Q3: Latest air temperature per plot
Q3_LATEST_AIR_TEMPERATURE = """
SELECT ?plot (MAX(?ts) AS ?latest_ts) ?temperature WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:airTemperature ?temperature .
}
GROUP BY ?plot ?temperature
ORDER BY DESC(?latest_ts)
"""

# Q4: Latest soil pH per plot
Q4_LATEST_SOIL_PH = """
SELECT ?plot (MAX(?ts) AS ?latest_ts) ?ph WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:soilPH ?ph .
}
GROUP BY ?plot ?ph
ORDER BY DESC(?latest_ts)
"""

# Q5: Plots under water stress (moisture < 20%)
Q5_WATER_STRESS_PLOTS = """
SELECT ?plot ?obs ?ts ?moisture ?quality WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:soilMoisture ?moisture .
    OPTIONAL { ?obs dq:qualityScore ?quality }
    FILTER (?moisture < 20.0)
}
ORDER BY ASC(?moisture)
"""

# Q6: Observations flagged as anomalies
Q6_ANOMALY_OBSERVATIONS = """
SELECT ?obs ?ts ?vendor ?quality WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:resultTime ?ts ;
         dq:anomalyFlag true .
    OPTIONAL { ?obs dq:vendorId ?vendor }
    OPTIONAL { ?obs dq:qualityScore ?quality }
}
ORDER BY DESC(?ts)
"""

# Q7: Quality score distribution per plot
Q7_QUALITY_DISTRIBUTION = """
SELECT ?plot (AVG(?quality) AS ?avg_quality) (MIN(?quality) AS ?min_quality)
       (MAX(?quality) AS ?max_quality) (COUNT(?obs) AS ?n) WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         dq:qualityScore ?quality .
}
GROUP BY ?plot
ORDER BY DESC(?avg_quality)
"""

# Q8: Non-reporting sensors (no obs for last 30 min)
# Note: SPARQL doesn't support date arithmetic universally — this version uses freshness
Q8_NON_REPORTING_SENSORS = """
SELECT ?sensor (MAX(?ts) AS ?last_seen) WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:madeBySensor ?sensor ;
         sosa:resultTime ?ts .
}
GROUP BY ?sensor
HAVING (MAX(?ts) < NOW() - "PT30M"^^xsd:duration)
ORDER BY ?last_seen
"""

# Q9: Irrigation state per plot
Q9_IRRIGATION_STATE = """
SELECT ?plot (MAX(?ts) AS ?latest_ts) ?irrigation_state WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:irrigationState ?irrigation_state .
}
GROUP BY ?plot ?irrigation_state
ORDER BY DESC(?latest_ts)
"""

# Q10: Low moisture BUT low confidence (audit query)
Q10_LOW_MOISTURE_LOW_CONFIDENCE = """
SELECT ?obs ?plot ?ts ?moisture ?quality ?unit_conf WHERE {
    ?obs rdf:type sosa:Observation ;
         sosa:hasFeatureOfInterest ?plot ;
         sosa:resultTime ?ts ;
         dq:soilMoisture ?moisture ;
         dq:qualityScore ?quality .
    OPTIONAL { ?obs dq:unitConfidence ?unit_conf }
    FILTER (?moisture < 20.0 && ?quality < 0.5)
}
ORDER BY ASC(?quality)
"""

ALL_QUERIES = {
    "Q1_latest_soil_moisture":       Q1_LATEST_SOIL_MOISTURE,
    "Q2_avg_moisture_last_hour":     Q2_AVG_MOISTURE_LAST_HOUR,
    "Q3_latest_air_temperature":     Q3_LATEST_AIR_TEMPERATURE,
    "Q4_latest_soil_ph":             Q4_LATEST_SOIL_PH,
    "Q5_water_stress_plots":         Q5_WATER_STRESS_PLOTS,
    "Q6_anomaly_observations":       Q6_ANOMALY_OBSERVATIONS,
    "Q7_quality_distribution":       Q7_QUALITY_DISTRIBUTION,
    "Q8_non_reporting_sensors":      Q8_NON_REPORTING_SENSORS,
    "Q9_irrigation_state":           Q9_IRRIGATION_STATE,
    "Q10_low_moisture_low_confidence": Q10_LOW_MOISTURE_LOW_CONFIDENCE,
}


def run_query(query_name: str, graph=None) -> tuple:
    """
    Run a named SPARQL query against the KG.
    
    Args:
        query_name: Name of the query from ALL_QUERIES
        graph: Optional rdflib Graph (uses in-memory KG if None)
    
    Returns:
        (results, success) where results is a list of dicts and success is bool
    """
    from pipeline.kg_manager import query_in_memory, get_in_memory_graph

    query_body = ALL_QUERIES.get(query_name)
    if query_body is None:
        logger.warning("Unknown query: %s", query_name)
        return [], False

    full_query = PREFIXES + "\n" + query_body

    if graph is not None:
        try:
            results = list(graph.query(full_query))
            rows = [{str(var): str(row[var]) for var in results.vars
                     if row[var] is not None}
                    for row in results]
            return rows, True
        except Exception as exc:
            logger.debug("Query %s failed on provided graph: %s", query_name, exc)
            return [], False

    # Use in-memory KG
    try:
        rows = query_in_memory(query_body)
        return rows, True
    except Exception as exc:
        logger.debug("Query %s failed: %s", query_name, exc)
        return [], False


def compute_qsr(observations_or_graph=None) -> float:
    """
    Compute QSR (Query Success Rate) = number of successful queries / 10.
    
    Runs all 10 standardized SPARQL queries against the knowledge graph.
    A query is "correct" if it executes without error (even if empty result).
    
    Args:
        observations_or_graph: rdflib Graph, list of observations, or None (uses in-memory KG)
    
    Returns:
        QSR in [0, 1]
    """
    graph = None

    if observations_or_graph is not None:
        try:
            from rdflib import Graph as RDFGraph
            if isinstance(observations_or_graph, RDFGraph):
                graph = observations_or_graph
            elif isinstance(observations_or_graph, list):
                # Build temporary graph from observations
                from pipeline.kg_manager import add_observation_to_memory
                for obs in observations_or_graph:
                    add_observation_to_memory(obs)
        except ImportError:
            pass

    correct = 0
    total = len(ALL_QUERIES)

    for query_name in ALL_QUERIES:
        _, success = run_query(query_name, graph=graph)
        if success:
            correct += 1

    qsr = correct / total if total > 0 else 0.0
    logger.debug("QSR: %d/%d = %.2f", correct, total, qsr)
    return qsr


def get_latest_soil_moisture(plot_id: str = None, graph=None) -> list:
    """Q1: Get latest soil moisture per plot."""
    rows, _ = run_query("Q1_latest_soil_moisture", graph=graph)
    if plot_id:
        rows = [r for r in rows if plot_id in r.get("plot", "")]
    return rows


def get_water_stress_plots(threshold: float = 20.0, graph=None) -> list:
    """Q5: Get plots under water stress."""
    rows, _ = run_query("Q5_water_stress_plots", graph=graph)
    return [r for r in rows if float(r.get("moisture", 100)) < threshold]


def get_anomaly_observations(graph=None) -> list:
    """Q6: Get observations flagged as anomalies."""
    rows, _ = run_query("Q6_anomaly_observations", graph=graph)
    return rows


def get_quality_distribution(graph=None) -> list:
    """Q7: Get quality score distribution per plot."""
    rows, _ = run_query("Q7_quality_distribution", graph=graph)
    return rows
