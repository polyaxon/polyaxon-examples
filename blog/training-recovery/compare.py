"""Compare trusted final checkpoints; reports evidence only after you run it."""

import argparse
import json

import torch


def same(left, right):
    if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
        return (left.dtype == right.dtype and left.shape == right.shape
                and torch.equal(left, right))
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("resumed")
    args = parser.parse_args()
    baseline = torch.load(args.baseline, map_location="cpu", weights_only=True)
    resumed = torch.load(args.resumed, map_location="cpu", weights_only=True)
    fields = ("contract", "next_epoch", "global_step", "model", "optimizer", "scheduler",
              "torch_rng", "shuffle_rng", "history")
    report = {field: same(baseline[field], resumed[field]) for field in fields}
    report["same_fields"] = baseline.keys() == resumed.keys()
    report["all_equal"] = all(report.values())
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["all_equal"] else 1)
