/**
 * sensor_node.c
 * Contiki-NG sensor node firmware for smart farm simulation.
 * Each node:
 *   - Is assigned a vendor type (A, B, C, D) based on node_id % 4
 *   - Generates realistic agricultural sensor data
 *   - Sends UDP payloads to the border router
 *   - Injects anomalies based on node_id patterns
 *   - Measures energy consumption via energest module
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include "sys/energest.h"
#include "dev/leds.h"
#include "sys/log.h"
#include "random.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

#define LOG_MODULE "SensorNode"
#define LOG_LEVEL LOG_LEVEL_INFO

/* UDP Configuration */
#define UDP_SERVER_PORT   5678
#define UDP_CLIENT_PORT   8765
#define SEND_INTERVAL     (30 * CLOCK_SECOND)

/* Base Unix timestamp for simulation start (~2025-02-19) */
#define SIM_BASE_TIMESTAMP 1740000000UL

/* Border router IPv6 address (link-local) */
static uip_ipaddr_t dest_ipaddr;

/* UDP connection */
static struct simple_udp_connection udp_conn;

/* Stuck-at detection */
static float last_moisture_value = -1.0;
static int stuck_at_count = 0;
#define STUCK_AT_THRESHOLD 5

/* Energest for energy measurement */
static energest_t cpu_start, lpm_start, tx_start, rx_start;

/* Process declaration */
PROCESS(sensor_node_process, "Sensor Node Process");
AUTOSTART_PROCESSES(&sensor_node_process);

/*---------------------------------------------------------------------------*/
/* Get vendor type based on node_id % 4 */
static char get_vendor_type(uint16_t node_id) {
    switch (node_id % 4) {
        case 0: return 'A';
        case 1: return 'B';
        case 2: return 'C';
        case 3: return 'D';
        default: return 'A';
    }
}

/*---------------------------------------------------------------------------*/
/* Generate realistic soil moisture (15-65%) */
static float gen_soil_moisture(uint16_t node_id, int reading_count) {
    float base = 35.0f + (float)(node_id % 20) - 10.0f;
    float noise = (float)(random_rand() % 200 - 100) / 100.0f * 5.0f;
    float val = base + noise;
    if (val < 15.0f) val = 15.0f;
    if (val > 65.0f) val = 65.0f;
    return val;
}

/* Generate realistic air temperature (5-38°C) */
static float gen_air_temperature(uint16_t node_id) {
    float base = 22.0f + (float)(node_id % 10) - 5.0f;
    float noise = (float)(random_rand() % 60 - 30) / 10.0f;
    float val = base + noise;
    if (val < 5.0f) val = 5.0f;
    if (val > 38.0f) val = 38.0f;
    return val;
}

/* Generate realistic soil pH (5.5-8.5) */
static float gen_soil_ph(uint16_t node_id) {
    float base = 6.8f + (float)(node_id % 6) / 10.0f - 0.3f;
    float noise = (float)(random_rand() % 20 - 10) / 100.0f;
    float val = base + noise;
    if (val < 5.5f) val = 5.5f;
    if (val > 8.5f) val = 8.5f;
    return val;
}

/* Get battery level (decreasing over time) */
static float get_battery_level(uint16_t node_id, int reading_count) {
    float base = 85.0f - (float)(reading_count % 100) * 0.15f;
    if (base < 5.0f) base = 5.0f;
    return base;
}

/*---------------------------------------------------------------------------*/
/* Anomaly injection based on node_id patterns */
static void inject_anomaly(char *buf, int buf_size, uint16_t node_id,
                            float *moisture, float *temperature, float *ph,
                            int reading_count, char vendor) {
    uint8_t node_last_digit = node_id % 10;
    float rand_prob = (float)(random_rand() % 100) / 100.0f;

    /* Node IDs ending in 3 or 7: range_outlier ~15% */
    if ((node_last_digit == 3 || node_last_digit == 7) && rand_prob < 0.15f) {
        if (random_rand() % 2 == 0) {
            *moisture = 110.0f + (float)(random_rand() % 50);   /* > 100% */
        } else {
            *temperature = 70.0f + (float)(random_rand() % 30); /* > 60°C */
        }
        LOG_INFO("ANOMALY: range_outlier injected, node=%u\n", node_id);
        return;
    }

    /* Node IDs ending in 5: stuck_at periodically */
    if (node_last_digit == 5 && (reading_count % (STUCK_AT_THRESHOLD + 1)) != 0) {
        if (last_moisture_value > 0.0f && stuck_at_count < STUCK_AT_THRESHOLD + 2) {
            *moisture = last_moisture_value;
            stuck_at_count++;
            LOG_INFO("ANOMALY: stuck_at injected, count=%d, node=%u\n", stuck_at_count, node_id);
        }
        return;
    }

    /* Node IDs ending in 9: timestamp_error ~10% (handled by border router) */
    /* Node IDs ending in 1: missing_field ~10% */
    if (node_last_digit == 1 && rand_prob < 0.10f) {
        *ph = -1.0f;  /* Signal missing field */
        LOG_INFO("ANOMALY: missing_field injected, node=%u\n", node_id);
        return;
    }

    /* Reset stuck_at for node 5 */
    if (node_last_digit == 5) {
        stuck_at_count = 0;
    }
}

/*---------------------------------------------------------------------------*/
/* Format payload according to vendor type */
static int format_payload(char *buf, int buf_size, char vendor, uint16_t node_id,
                           float moisture, float temperature, float ph, float battery,
                           unsigned long timestamp, int inject_ts_error) {
    int len = 0;
    char plot_id[8];
    snprintf(plot_id, sizeof(plot_id), "P%d", (node_id % 6) + 1);

    /* Timestamp anomaly for nodes ending in 9 */
    unsigned long ts = timestamp;
    if (inject_ts_error) {
        ts = timestamp + 86400;  /* +24h in future */
    }

    switch (vendor) {
        case 'A':  /* Clean JSON */
            if (ph >= 0) {
                len = snprintf(buf, buf_size,
                    "{\"deviceId\":\"%u\",\"ts\":\"%lu\",\"soilMoisture\":%.1f,"
                    "\"airTemperature\":%.1f,\"soilPH\":%.2f,\"batteryLevel\":%.1f,"
                    "\"unit\":\"%%\",\"plot\":\"%s\"}",
                    node_id, ts, moisture, temperature, ph, battery, plot_id);
            } else {
                len = snprintf(buf, buf_size,
                    "{\"deviceId\":\"%u\",\"ts\":\"%lu\",\"soilMoisture\":%.1f,"
                    "\"airTemperature\":%.1f,\"batteryLevel\":%.1f,"
                    "\"unit\":\"%%\",\"plot\":\"%s\"}",
                    node_id, ts, moisture, temperature, battery, plot_id);
            }
            break;

        case 'B':  /* Epoch + fraction */
            len = snprintf(buf, buf_size,
                "{\"id\":\"%u\",\"time\":%lu,\"sm\":%.4f,\"sm_unit\":\"vwc\","
                "\"field\":\"plot-%d\",\"temp_c\":%.1f,\"ph\":%.2f,\"battery\":%.1f}",
                node_id, ts, moisture / 100.0f, (node_id % 6) + 1,
                temperature, (ph >= 0 ? ph : 6.8f), battery);
            break;

        case 'C':  /* Nested + permille */
            len = snprintf(buf, buf_size,
                "{\"meta\":{\"dev\":\"%u\",\"plot\":\"%s\"},"
                "\"obs\":{\"t\":\"%lu\",\"val\":%d},"
                "\"type\":\"SOIL_MOIST\",\"scale\":\"permille\","
                "\"airTemperature\":%.1f,\"soilPH\":%.2f}",
                node_id, plot_id, ts, (int)(moisture * 10),
                temperature, (ph >= 0 ? ph : 6.8f));
            break;

        case 'D':  /* Compact */
            len = snprintf(buf, buf_size,
                "{\"d\":\"%u\",\"t\":%lu,\"m\":%d,\"k\":\"SM\","
                "\"temp\":%d,\"ph_x10\":%d,\"batt\":%d}",
                node_id, ts, (int)moisture, (int)temperature,
                (ph >= 0 ? (int)(ph * 10) : 68), (int)battery);
            break;

        default:
            len = 0;
    }
    return len;
}

/*---------------------------------------------------------------------------*/
/* Log energest energy consumption */
static void log_energest(uint16_t node_id) {
    energest_flush();
    uint64_t cpu   = energest_type_time(ENERGEST_TYPE_CPU)   - cpu_start;
    uint64_t lpm   = energest_type_time(ENERGEST_TYPE_LPM)   - lpm_start;
    uint64_t tx    = energest_type_time(ENERGEST_TYPE_TRANSMIT) - tx_start;
    uint64_t rx    = energest_type_time(ENERGEST_TYPE_LISTEN)   - rx_start;

    LOG_INFO("ENERGY node=%u CPU=%llu LPM=%llu TX=%llu RX=%llu\n",
             node_id, (unsigned long long)cpu, (unsigned long long)lpm,
             (unsigned long long)tx, (unsigned long long)rx);
}

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(sensor_node_process, ev, data) {
    static struct etimer timer;
    static int reading_count = 0;
    char buf[512];

    PROCESS_BEGIN();

    uint16_t node_id = linkaddr_node_addr.u8[7] + (linkaddr_node_addr.u8[6] << 8);
    if (node_id == 0) node_id = 1;  /* Safety: avoid node_id = 0 */

    char vendor = get_vendor_type(node_id);

    LOG_INFO("Sensor node %u starting, vendor=%c\n", node_id, vendor);

    /* Initialize UDP */
    simple_udp_register(&udp_conn, UDP_CLIENT_PORT, NULL,
                        UDP_SERVER_PORT, NULL);

    /* Set border router address (default route) */
    uip_ip6addr(&dest_ipaddr, 0xfe80, 0, 0, 0, 0x0212, 0x7400, 0x0001, 0x0101);

    /* Initialize energest */
    energest_init();
    cpu_start = energest_type_time(ENERGEST_TYPE_CPU);
    lpm_start = energest_type_time(ENERGEST_TYPE_LPM);
    tx_start  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    rx_start  = energest_type_time(ENERGEST_TYPE_LISTEN);

    etimer_set(&timer, SEND_INTERVAL);

    while(1) {
        PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&timer));
        etimer_reset(&timer);

        reading_count++;

        /* Generate sensor readings */
        float moisture    = gen_soil_moisture(node_id, reading_count);
        float temperature = gen_air_temperature(node_id);
        float ph          = gen_soil_ph(node_id);
        float battery     = get_battery_level(node_id, reading_count);

        /* Check if we should inject timestamp anomaly (nodes ending in 9) */
        int inject_ts = (node_id % 10 == 9 &&
                         (float)(random_rand() % 100) / 100.0f < 0.10f);

        /* Inject anomalies */
        inject_anomaly(buf, sizeof(buf), node_id, &moisture, &temperature,
                       &ph, reading_count, vendor);

        /* Update stuck-at tracking */
        if (node_id % 10 != 5) {
            last_moisture_value = moisture;
        }

        /* Format payload */
        unsigned long sim_time = clock_time() / CLOCK_SECOND + SIM_BASE_TIMESTAMP;
        int len = format_payload(buf, sizeof(buf), vendor, node_id,
                                 moisture, temperature, ph, battery,
                                 sim_time, inject_ts);

        if (len > 0) {
            simple_udp_sendto(&udp_conn, buf, len, &dest_ipaddr);
            LOG_INFO("TX vendor=%c node=%u seq=%d payload=%s\n",
                     vendor, node_id, reading_count, buf);
            leds_toggle(LEDS_RED);
        }

        /* Log energy every 10 readings */
        if (reading_count % 10 == 0) {
            log_energest(node_id);
        }
    }

    PROCESS_END();
}
