/**
 * border_router.c
 * Contiki-NG border router firmware for smart farm simulation.
 * Receives UDP payloads from sensor nodes and logs to serial output.
 * Tracks per-node statistics (packets received, last seen timestamp).
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include "sys/log.h"
#include <stdio.h>
#include <string.h>

#define LOG_MODULE "BorderRouter"
#define LOG_LEVEL LOG_LEVEL_INFO

/* UDP configuration */
#define UDP_SERVER_PORT 5678
#define MAX_NODES       64

/* Per-node statistics */
typedef struct {
    uint16_t node_id;
    uint32_t packets_received;
    unsigned long last_seen;
    char last_payload[256];
} node_stats_t;

static node_stats_t node_stats[MAX_NODES];
static int n_known_nodes = 0;

static struct simple_udp_connection udp_conn;

PROCESS(border_router_process, "Border Router Process");
AUTOSTART_PROCESSES(&border_router_process);

/*---------------------------------------------------------------------------*/
static node_stats_t* find_or_create_node(uint16_t node_id) {
    for (int i = 0; i < n_known_nodes; i++) {
        if (node_stats[i].node_id == node_id) {
            return &node_stats[i];
        }
    }
    if (n_known_nodes < MAX_NODES) {
        node_stats[n_known_nodes].node_id = node_id;
        node_stats[n_known_nodes].packets_received = 0;
        n_known_nodes++;
        return &node_stats[n_known_nodes - 1];
    }
    return NULL;
}

/*---------------------------------------------------------------------------*/
static void udp_rx_callback(struct simple_udp_connection *c,
                             const uip_ipaddr_t *sender_addr,
                             uint16_t sender_port,
                             const uip_ipaddr_t *receiver_addr,
                             uint16_t receiver_port,
                             const uint8_t *data,
                             uint16_t datalen) {
    if (datalen == 0 || datalen >= 512) {
        return;
    }

    /* Extract node ID from sender address */
    uint16_t node_id = sender_addr->u8[15] + (sender_addr->u8[14] << 8);

    /* Update statistics */
    node_stats_t *stats = find_or_create_node(node_id);
    if (stats != NULL) {
        stats->packets_received++;
        stats->last_seen = clock_time() / CLOCK_SECOND;
        memcpy(stats->last_payload, data, datalen < 255 ? datalen : 255);
        stats->last_payload[datalen < 255 ? datalen : 255] = '\0';
    }

    /* Log payload to serial output (for Python bridge) */
    LOG_INFO("RX node=%u seq=%lu payload=%.*s\n",
             node_id,
             stats ? (unsigned long)stats->packets_received : 0UL,
             (int)datalen, (char *)data);
}

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(border_router_process, ev, data) {
    static struct etimer stats_timer;

    PROCESS_BEGIN();

    LOG_INFO("Border router starting\n");

    /* Register UDP listener */
    simple_udp_register(&udp_conn, UDP_SERVER_PORT, NULL, 0, udp_rx_callback);

    /* Start RPL as root */
    NETSTACK_ROUTING.root_start();

    etimer_set(&stats_timer, 60 * CLOCK_SECOND);  /* Print stats every 60s */

    while(1) {
        PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&stats_timer));
        etimer_reset(&stats_timer);

        /* Print per-node statistics */
        LOG_INFO("STATS: %d nodes tracked\n", n_known_nodes);
        for (int i = 0; i < n_known_nodes; i++) {
            LOG_INFO("  node=%u pkts=%lu last_seen=%lus\n",
                     node_stats[i].node_id,
                     (unsigned long)node_stats[i].packets_received,
                     (unsigned long)node_stats[i].last_seen);
        }
    }

    PROCESS_END();
}
