"""
cooja/scripts/extract_metrics.py
Extract metrics from Cooja simulation log files.
Parses RX payloads and computes PDR, energy, latency.
"""

import re
import json
import sys
import csv
import os
from datetime import datetime


def parse_cooja_log(log_file: str) -> dict:
    """Parse a Cooja simulation log file."""
    rx_payloads = []
    energy_records = []
    stats_records = []

    rx_pattern = re.compile(
        r'RX node=(\d+) seq=(\d+) payload=(\{.*\})'
    )
    energy_pattern = re.compile(
        r'ENERGY node=(\d+) CPU=(\d+) LPM=(\d+) TX=(\d+) RX=(\d+)'
    )
    stats_pattern = re.compile(
        r'node=(\d+) pkts=(\d+) last_seen=(\d+)s'
    )

    with open(log_file, 'r', errors='replace') as f:
        for line in f:
            m = rx_pattern.search(line)
            if m:
                try:
                    payload = json.loads(m.group(3))
                    rx_payloads.append({
                        'node_id': int(m.group(1)),
                        'seq': int(m.group(2)),
                        'payload': payload,
                    })
                except json.JSONDecodeError:
                    pass

            m = energy_pattern.search(line)
            if m:
                energy_records.append({
                    'node_id': int(m.group(1)),
                    'cpu': int(m.group(2)),
                    'lpm': int(m.group(3)),
                    'tx': int(m.group(4)),
                    'rx': int(m.group(5)),
                })

            m = stats_pattern.search(line)
            if m:
                stats_records.append({
                    'node_id': int(m.group(1)),
                    'packets': int(m.group(2)),
                    'last_seen': int(m.group(3)),
                })

    # Compute PDR per node
    tx_counts = {}
    for p in rx_payloads:
        nid = p['node_id']
        tx_counts[nid] = max(tx_counts.get(nid, 0), p['seq'])

    node_rx = {}
    for p in rx_payloads:
        nid = p['node_id']
        node_rx[nid] = node_rx.get(nid, 0) + 1

    pdr_per_node = {}
    for nid, tx in tx_counts.items():
        rx = node_rx.get(nid, 0)
        pdr_per_node[nid] = rx / tx if tx > 0 else 0.0

    return {
        'n_rx_payloads': len(rx_payloads),
        'n_nodes': len(set(p['node_id'] for p in rx_payloads)),
        'payloads': rx_payloads,
        'energy': energy_records,
        'stats': stats_records,
        'pdr_per_node': pdr_per_node,
        'avg_pdr': sum(pdr_per_node.values()) / len(pdr_per_node) if pdr_per_node else 0.0,
    }


def save_payloads_csv(payloads: list, output_file: str):
    """Save extracted payloads to CSV for pipeline processing."""
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    if not payloads:
        return

    fields = ['node_id', 'seq'] + list(payloads[0]['payload'].keys())
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for p in payloads:
            row = {'node_id': p['node_id'], 'seq': p['seq']}
            row.update(p['payload'])
            writer.writerow(row)
    print(f"Saved {len(payloads)} payloads to {output_file}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract_metrics.py <log_file> [output_csv]")
        sys.exit(1)

    log_file = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else 'results/cooja_payloads.csv'

    metrics = parse_cooja_log(log_file)
    print(f"Parsed log: {metrics['n_rx_payloads']} payloads from {metrics['n_nodes']} nodes")
    print(f"Average PDR: {metrics['avg_pdr']:.2%}")

    if metrics['payloads']:
        save_payloads_csv(metrics['payloads'], output_csv)
