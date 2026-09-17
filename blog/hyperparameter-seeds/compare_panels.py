"""Compare two downloaded single-configuration panels, never silently drop trials."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from study import summarize


def load_panel(root, label):
    plans = list(root.rglob("plan.json"))
    if len(plans) != 1:
        raise ValueError(f"{root}: expected exactly one plan.json, found {len(plans)}")
    plan_path = plans[0]
    plan = json.loads(plan_path.read_text())
    if set(plan["candidates_alpha"]) != {"sampled"}:
        raise ValueError("Expected a single-configuration random-search child panel")
    alpha = plan["candidates_alpha"]["sampled"]
    records = [json.loads(path.read_text()) for path in sorted(plan_path.parent.glob("trial-*.json"))]
    for row in records:
        if row["candidate"] != "sampled" or row["alpha"] != alpha:
            raise ValueError("Trial configuration differs from its plan")
        if row["status"] == "completed":
            if row["completed_epochs"] != plan["epochs"]:
                raise ValueError("Training budget differs from its plan")
            if not all(math.isfinite(row[key]) for key in ("validation_macro_f1", "fit_seconds")):
                raise ValueError("Nonfinite score or fit time")
        row["candidate"] = label
    return plan, records, {"plan_path": str(plan_path.resolve()),
                           "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path, help="Downloaded artifacts for candidate A")
    parser.add_argument("right", type=Path, help="Downloaded artifacts for candidate B")
    args = parser.parse_args()
    left, a, left_source = load_panel(args.left, "A")
    right, b, right_source = load_panel(args.right, "B")
    for key in ("training_seeds", "epochs", "loss", "learning_rate", "eta0", "split_seeds",
                "metric", "labels", "dataset", "data_sha256", "manifest_sha256", "source_sha256", "runtime"):
        if left[key] != right[key]:
            raise ValueError(f"Panels are not comparable: {key} differs")
    candidates = {"A": left["candidates_alpha"]["sampled"],
                  "B": right["candidates_alpha"]["sampled"]}
    if candidates["A"] == candidates["B"]:
        raise ValueError("Choose two different configurations, not copies of the same panel")
    summary = summarize(a + b, candidates, left["training_seeds"])
    summary.update(candidates_alpha=candidates, sources={"A": left_source, "B": right_source})
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if summary["status"] == "complete" else 1)
