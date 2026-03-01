# 🌾 AgriSem Framework

**Framework de médiation sémantique quality-aware pour l'IoT agricole**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Fuseki](https://img.shields.io/badge/Fuseki-4.10.0-orange)](https://jena.apache.org/documentation/fuseki2/)

---

## 📋 Table des matières

1. [Présentation](#présentation)
2. [Prérequis](#prérequis)
3. [Installation et lancement](#installation-et-lancement)
4. [Architecture](#architecture)
5. [Structure du projet](#structure-du-projet)
6. [Formules mathématiques](#formules-mathématiques)
7. [Pipeline en 8 étapes](#pipeline-en-8-étapes)
8. [Heterogénéité vendors](#hétérogénéité-vendors)
9. [API REST](#api-rest)
10. [Expérimentation](#expérimentation)
11. [Figures](#figures)

---

## Présentation

AgriSem Framework est un système de médiation sémantique pour l'IoT agricole qui :

- **Collecte** les données de capteurs Contiki/Cooja (Sky Motes : pH, température, turbidité, ammoniaque, oxygène, humidité sol/air)
- **Gère l'hétérogénéité** de 4 formats vendors différents via routage automatique
- **Normalise** les unités (fraction→%, permille→%, °F→°C, epoch→ISO)
- **Valide** avec 15 contraintes SHACL
- **Répare** automatiquement les anomalies réparables
- **Calcule** un score de qualité Q(o) ∈ [0,1] selon 5 facteurs
- **Insère** les observations annotées dans Apache Jena Fuseki (SOSA/SSN)
- **Décide** les actions agronomiques pondérées par la qualité

Le projet s'appuie sur la simulation **daksh-patel-nitw/Smart-Farming-IOT** (Contiki 2.7 / Cooja).

---

## Prérequis

| Outil | Version minimale | Obligatoire |
|-------|-----------------|-------------|
| Python | 3.8+ | ✅ |
| Docker | 20.10+ | ⚠️ (optionnel, pour Fuseki) |
| Docker Compose | 2.0+ | ⚠️ (optionnel) |

---

## Installation et lancement

### Lancement rapide (mode standalone — sans Cooja, sans Docker)

```bash
git clone https://github.com/ahmedamamou/projet2.git
cd projet2
./start.sh --standalone
```

### Lancement avec Cooja et Fuseki

```bash
./start.sh --live
```

### Ce que fait `start.sh`

1. Vérifie Python 3.8+ et Docker
2. Crée un environnement virtuel Python et installe les dépendances
3. Lance Apache Jena Fuseki via Docker Compose (port 3030)
4. Attend que Fuseki soit prêt (health check)
5. Crée le dataset `agrisem` dans Fuseki
6. Charge l'ontologie SOSA/SSN
7. Lance le serveur Flask (port 12345)
8. Affiche les URLs

### Arrêt

```bash
./stop.sh
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgriSem Framework                           │
│                                                                 │
│  [Cooja/Sky Motes] ──► [cooja_bridge] ──► [vendor_router]      │
│         │                                        │             │
│         │              LIVE mode              STANDALONE mode   │
│         └─────────────────────────────────────────┘            │
│                                │                               │
│                         [normalizer]                           │
│                     (fraction/permille/°F/epoch)               │
│                                │                               │
│                         [validator]                            │
│                     (15 SHACL shapes)                          │
│                                │                               │
│                         [repairer]                             │
│                     (clamp + flagging)                         │
│                                │                               │
│                      [quality_scorer]                          │
│                   Q(o) = Σ wᵢ·fᵢ(o)                           │
│                                │                               │
│                       [kg_manager]                             │
│               Apache Jena Fuseki (SPARQL/SOSA)                 │
│                                │                               │
│                        [reasoner]                              │
│               Confiance(A) ≥ τ_A → action                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Structure du projet

```
projet2/
├── start.sh                    # Lancement unique
├── stop.sh                     # Arrêt propre
├── server.py                   # Serveur Flask principal (port 12345)
├── requirements.txt            # Dépendances Python
├── docker-compose.yml          # Apache Jena Fuseki
├── .gitignore
├── LICENSE
│
├── config/
│   ├── vendor_profiles.yaml    # Profils des 4 vendors
│   ├── anomaly_config.yaml     # Types et taux d'anomalies
│   ├── experiment_config.yaml  # Matrice expérimentale 840+ runs
│   └── thresholds.yaml         # Seuils de décision par action
│
├── semantic/
│   ├── ontology.ttl            # Ontologie SOSA/SSN + Agriculture + DQ
│   └── shacl_shapes.ttl        # 15 SHACL shapes (10 basiques + 5 avancés)
│
├── mapping/
│   ├── vendor_a.rml.ttl        # RML mapping Vendor A (JSON clair, %)
│   ├── vendor_b.rml.ttl        # RML mapping Vendor B (epoch, fraction, °F)
│   ├── vendor_c.rml.ttl        # RML mapping Vendor C (imbriqué, permille)
│   └── vendor_d.rml.ttl        # RML mapping Vendor D (compact, entiers)
│
├── pipeline/
│   ├── cooja_bridge.py         # Parse données Cooja + fetch IPv6
│   ├── vendor_router.py        # Routage vers format vendor
│   ├── normalizer.py           # Normalisation d'unités
│   ├── validator.py            # Validation SHACL-like
│   ├── repairer.py             # Réparation + flagging
│   ├── quality_scorer.py       # Calcul Q(o)
│   ├── kg_manager.py           # Gestion Fuseki
│   ├── reasoner.py             # Décision quality-aware
│   └── provenance.py           # Traçabilité PROV-O
│
├── generator/
│   ├── payload_generator.py    # Génération données synthétiques
│   └── anomaly_injector.py     # Injection d'anomalies contrôlées
│
├── evaluation/
│   ├── metrics.py              # QSR, F1, latence, overhead
│   ├── baselines.py            # B1-ETL, B2-RDF-naïf, B3-SHACL-no-Q
│   ├── ablations.py            # -SHACL, -UnitNorm, -QualityScore, -Repair
│   ├── run_experiments.py      # Orchestrateur 840+ runs
│   └── generate_figures.py     # 8 figures publication-ready
│
├── sparql/
│   └── queries.sparql          # 10 requêtes SPARQL pour QSR
│
├── cooja/
│   └── test.csc                # Simulation Cooja originale (XML)
│
└── results/                    # Résultats CSV et figures (gitignorés)
    └── figures/
```

---

## Formules mathématiques

### Quality Score Q(o)

$$Q(o) = \sum_{i=1}^{5} w_i \cdot f_i(o), \quad \sum w_i = 1, \quad f_i \in [0,1]$$

**Poids par défaut :** `w = [0.20, 0.25, 0.15, 0.25, 0.15]`

| Facteur | Formule | Description |
|---------|---------|-------------|
| f₁ | \|champs présents\| / \|champs requis\| | Complétude |
| f₂ | `{1.0 native, 0.8 conv. connue, 0.5 heuristique, 0.2 inconnu}` | Confiance unité |
| f₃ | `max(0, 1 - (t_now - t_obs) / T_max)`, T_max=1800s | Fraîcheur |
| f₄ | sigmoïde douce aux bornes SHACL | Plausibilité |
| f₅ | `1 - (nb_violations_récentes / N_fenêtre)`, N=100 | Fiabilité capteur |

### Décision quality-aware

$$\text{Confiance}(A) = \frac{\sum Q(o)}{|O_A|}$$

$$\text{Déclencher } A \iff \text{Confiance}(A) \geq \tau_A$$

| Action | Seuil τ_A |
|--------|-----------|
| Sécheresse | 0.65 |
| Irrigation | 0.70 |
| Fertilisation | 0.75 |
| Gel | 0.80 |

---

## Pipeline en 8 étapes

| Étape | Module | Description |
|-------|--------|-------------|
| 1 | `cooja_bridge.py` | Parse `"ph:7 Temp:25 turb:30 am:5 ox:8 mo:35 hu:55"` |
| 2 | `vendor_router.py` | Simule 4 formats hétérogènes (A/B/C/D) |
| 3 | `normalizer.py` | Normalise fraction→%, permille→%, °F→°C, epoch→ISO |
| 4 | `validator.py` | 15 SHACL shapes (plages, types, cohérence, timestamp) |
| 5 | `repairer.py` | Clamp valeurs proches des bornes, flag anomalies sévères |
| 6 | `quality_scorer.py` | Q(o) = Σ wᵢ · fᵢ(o) |
| 7 | `kg_manager.py` | INSERT SPARQL dans Fuseki (SOSA/SSN + DQ annotations) |
| 8 | `reasoner.py` | Confiance(A) ≥ τ_A → décision |

---

## Hétérogénéité vendors

| Nœud | Vendor | Format | Particularités |
|------|--------|--------|----------------|
| node_2 | **A** | JSON clair | %, ISO 8601 |
| node_3 | **B** | Epoch + fraction | epoch_ms, fraction 0-1, °F |
| node_4 | **C** | JSON imbriqué | permille (‰) |
| node_5 | **D** | Compact | clés courtes, entiers, epoch_s |
| node_6 | **A** | JSON clair | %, ISO 8601 (2ème instance) |

### Adresses IPv6 Cooja

```
node_2 : http://[aaaa::212:7402:2:202]
node_3 : http://[aaaa::212:7403:3:303]
node_4 : http://[aaaa::212:7404:4:404]
node_5 : http://[aaaa::212:7405:5:505]
node_6 : http://[aaaa::212:7406:6:606]
```

---

## API REST

### `GET /` — Pipeline complet

```bash
curl http://localhost:12345/
```

Réponse :
```json
{
  "status": "ok",
  "mode": "standalone",
  "n_observations": 5,
  "average_Q": 0.8324,
  "observations": [...],
  "decision": {
    "actions": ["irrigation"],
    "confidence": 0.812,
    "decisions": {...}
  },
  "pipeline_ms": 45.2
}
```

### `GET /metrics` — Métriques agrégées

```bash
curl http://localhost:12345/metrics
```

### `GET /health` — Health check

```bash
curl http://localhost:12345/health
```

### `POST /sendAccutatorSignal` — Déclenchement actionneur

```bash
curl -X POST http://localhost:12345/sendAccutatorSignal \
  -H "Content-Type: application/json" \
  -d '{"observations": [...]}'
```

---

## Expérimentation

### Lancer les expériences (840+ runs)

```bash
source venv/bin/activate
python -m evaluation.run_experiments
```

### Générer les 8 figures

```bash
python -m evaluation.generate_figures
```

Les figures sont sauvegardées dans `results/figures/`.

---

## Figures

| Figure | Description |
|--------|-------------|
| Fig. 1 | QSR en fonction du taux d'anomalies |
| Fig. 2 | F1-score de détection d'anomalies |
| Fig. 3 | Latence E2E en fonction du volume |
| Fig. 4 | Comparaison avec baselines et ablations |
| Fig. 5 | QSR par vendor (hétérogénéité) |
| Fig. 6 | Radar des facteurs de qualité f₁..f₅ |
| Fig. 7 | Taux de réparation automatique |
| Fig. 8 | Distribution de la confiance et seuils de décision |

---

## SHACL Shapes (15)

**Basiques (10) :**
ObservationStructure, ResultValue, TemperatureRange(-40..60°C),
HumidityRange(0..100%), MoistureRange(0..100%), PHRange(0..14),
OxygenRange(0..20 mg/L), AmmoniaRange(0..10 mg/L), TurbidityRange(0..500 NTU), TimestampType

**Avancées (5) :**
TimestampNotFuture, SpatialCoherence, StuckAtDetection, CrossProperty, ProvenanceCompleteness

---

## Licence

MIT — voir [LICENSE](LICENSE)
