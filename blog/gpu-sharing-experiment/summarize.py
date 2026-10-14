"""Summarize downloaded worker artifacts over their common active interval."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def quantile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("workers", nargs="+", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    meta = [json.loads((path / "worker.json").read_text()) for path in a.workers]
    first = meta[0]
    keys = ["experiment", "mode", "count", "node", "seconds", "torch", "cuda", "planned_start", "device"]
    if any(any(row[key] != first[key] for key in keys) for row in meta):
        raise ValueError("These workers do not belong to one comparable cohort.")
    if sorted(row["replica"] for row in meta) != list(range(first["count"])):
        raise ValueError("Missing or duplicate replicas: the cohort is incomplete.")
    start, end = max(row["started"] for row in meta), min(row["finished"] for row in meta)
    if end - start < first["seconds"] * 0.8:
        raise ValueError("Insufficient common measurement interval.")
    rows, by_workload = [], defaultdict(list)
    for path, m in zip(a.workers, meta):
        batches = [json.loads(line) for line in (path / "batches.jsonl").read_text().splitlines()]
        kept = [row for row in batches if row["start"] >= start and row["end"] <= end]
        if not kept:
            raise ValueError("No complete batches in the common interval.")
        rate = sum(row["samples"] for row in kept) / (end - start)
        row = {"replica": m["replica"], "workload": m["workload"], "samples_per_second": rate,
               "batch_p50_seconds": quantile([r["seconds"] for r in kept], 0.5),
               "batch_p99_seconds": quantile([r["seconds"] for r in kept], 0.99),
               "batches": len(kept), "visible_memory_bytes": m["visible_memory_bytes"]}
        rows.append(row)
        by_workload[m["workload"]].append(rate)
    result = {"experiment": first["experiment"], "mode": first["mode"], "node": first["node"],
              "common_seconds": end-start, "workers": rows,
              "rates_by_workload": {name: sum(rates) for name, rates in by_workload.items()},
              "scope": "batch execution latency, not HTTP latency or open-loop service capacity"}
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
