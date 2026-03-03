# Cooja Simulation Files — AgriSem Smart Farming

This project uses **Contiki 2.7** and the **Cooja** network simulator (NOT Contiki-NG).
All simulation files use the `se.sics.cooja.*` package namespace.

## Prerequisites

- Contiki 2.7 installed (e.g., in `~/contiki`)
- Cooja simulator (located at `~/contiki/tools/cooja`)
- Java 8 or later

## How to Open a Simulation in Cooja

1. Start Cooja:
   ```
   cd ~/contiki/tools/cooja
   ant run
   ```
2. In Cooja, go to **File → Open simulation → Browse** and select one of the `.csc` files from this directory.
3. Click **Start** to run the simulation.

> **Note:** The simulation files reference `[CONTIKI_DIR]` which Cooja resolves automatically to your Contiki installation path.

## Simulation Files

### `test.csc`
- **Nodes:** 1 Border Router (sky1) + 5 Sensor nodes (sky2)
- **Purpose:** Basic test/demo simulation for the AgriSem framework
- **Radio:** UDGM, TX range 50 m, interference 100 m, 0% loss

### `simulations/smart_farm_10nodes.csc`
- **Nodes:** 1 Border Router (sky1) + 10 Sensor nodes (sky2)
- **Topology:** Grid 2×5, spacing ~30 m
- **Radio:** UDGM, TX range 50 m, interference 100 m, 0% loss
- **Random seed:** 123456

### `simulations/smart_farm_25nodes.csc`
- **Nodes:** 1 Border Router (sky1) + 25 Sensor nodes (sky2)
- **Topology:** Grid 5×5, spacing ~25 m
- **Radio:** UDGM, TX range 50 m, interference 100 m, 0% loss
- **Random seed:** 234567

### `simulations/smart_farm_50nodes.csc`
- **Nodes:** 1 Border Router (sky1) + 50 Sensor nodes (sky2)
- **Topology:** Grid 5×10, spacing ~20 m
- **Radio:** UDGM, TX range 45 m, interference 90 m, 0% loss
- **Random seed:** 345678

## Plugins Included in Each Simulation

| Plugin | Description |
|--------|-------------|
| `SimControl` | Start/stop/step the simulation |
| `Visualizer` | Visual map of mote positions and radio links |
| `LogListener` | Live serial output from all motes |
| `TimeLine` | Per-mote radio and LED activity timeline |
| `PowerTracker` | Energy consumption statistics per mote |

## Mote Types

| Identifier | Type | Firmware |
|------------|------|----------|
| `sky1` | Border Router | `examples/ipv6/rpl-border-router/border-router.sky` |
| `sky2` | Sensor Node | `examples/ipv6/sky-websense/sky-websense.sky` |

## How to Change Packet Loss Rate

Open the `.csc` file in a text editor and modify the `success_ratio_rx` value inside the `<radiomedium>` block:

```xml
<radiomedium>
  se.sics.cooja.radiomediums.UDGM
  <transmitting_range>50.0</transmitting_range>
  <interference_range>100.0</interference_range>
  <success_ratio_tx>1.0</success_ratio_tx>
  <success_ratio_rx>1.0</success_ratio_rx>   <!-- Change this value -->
</radiomedium>
```

| `success_ratio_rx` value | Packet loss rate |
|--------------------------|-----------------|
| `1.0`                    | 0% loss         |
| `0.95`                   | 5% loss         |
| `0.85`                   | 15% loss        |
| `0.70`                   | 30% loss        |
