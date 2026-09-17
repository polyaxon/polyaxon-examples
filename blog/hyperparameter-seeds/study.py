"""Compare two fixed SGD recipes over a predeclared seed panel on validation data."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import numpy as np
import sklearn
from sklearn.datasets import load_digits
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits


CANDIDATES = {"A": 0.0001, "B": 0.01}
SEEDS = [11, 23, 37, 53, 71]
EPOCHS = 40
LABELS = np.arange(10)


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


def describe(values):
    return {"n": len(values), "mean": statistics.mean(values),
            "sample_sd": statistics.stdev(values), "min": min(values), "max": max(values)}


def train(alpha, seed, x_train, y_train):
    model = SGDClassifier(loss="log_loss", penalty="l2", alpha=alpha,
                          learning_rate="constant", eta0=0.01, shuffle=False,
                          random_state=seed, early_stopping=False, tol=None)
    order_rng = np.random.default_rng(seed)
    for _ in range(EPOCHS):
        order = order_rng.permutation(len(y_train))
        # partial_fit performs one pass. Both candidates receive the same orders.
        model.partial_fit(x_train[order], y_train[order], classes=LABELS)
    return model


def summarize(records):
    expected = {(candidate, seed) for candidate in CANDIDATES for seed in SEEDS}
    observed = [(row["candidate"], row["seed"]) for row in records]
    complete = (len(observed) == len(expected) and set(observed) == expected
                and all(row["status"] == "completed" for row in records))
    if not complete:
        return {"status": "incomplete", "expected_trials": len(expected),
                "completed_trials": sum(row["status"] == "completed" for row in records),
                "message": "Resolve missing, duplicate, or failed trials before comparing finalists."}
    by_pair = {(row["candidate"], row["seed"]): row for row in records}
    paired = [{"seed": seed, "A": by_pair["A", seed]["validation_macro_f1"],
               "B": by_pair["B", seed]["validation_macro_f1"],
               "B_minus_A": (by_pair["B", seed]["validation_macro_f1"]
                             - by_pair["A", seed]["validation_macro_f1"])} for seed in SEEDS]
    deltas = [pair["B_minus_A"] for pair in paired]
    return {"status": "complete", "scope": "training-seed variation on one fixed validation split",
            "candidates": {name: {
                "validation_macro_f1": describe([by_pair[name, seed]["validation_macro_f1"]
                                                  for seed in SEEDS]),
                "fit_seconds": describe([by_pair[name, seed]["fit_seconds"] for seed in SEEDS])
            } for name in CANDIDATES},
            "paired_scores": paired, "paired_difference": describe(deltas),
            "B_higher_count": sum(delta > 0 for delta in deltas),
            "A_higher_count": sum(delta < 0 for delta in deltas),
            "exact_tie_count": sum(delta == 0 for delta in deltas),
            "decision": "No automatic winner. Review effect size, variation, failures, and class-level errors."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/seed-study"))
    parser.add_argument("--tracked", action="store_true")
    args = parser.parse_args()
    tracking = None
    output = args.output
    if args.tracked:
        from polyaxon import tracking

        tracking.init()
        output = Path(tracking.get_outputs_path()) / "seed-study"
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("Use an empty output directory; previous trial records must not be overwritten.")

    x, y = load_digits(return_X_y=True)
    indices = np.arange(len(y))
    development, held_out = train_test_split(indices, test_size=0.2, stratify=y, random_state=101)
    training, validation = train_test_split(development, test_size=0.25,
                                           stratify=y[development], random_state=202)
    manifest = {"training": training.tolist(), "validation": validation.tolist(),
                "reserved_test": held_out.tolist()}
    save_json(output / "split-manifest.json", manifest)
    scaler = StandardScaler().fit(x[training])
    x_train, x_validation = scaler.transform(x[training]), scaler.transform(x[validation])
    # Reserved test rows are not transformed, scored, or used for selection.
    plan = {"candidates_alpha": CANDIDATES, "training_seeds": SEEDS, "epochs": EPOCHS,
            "loss": "log_loss", "learning_rate": "constant", "eta0": 0.01,
            "split_seeds": [101, 202], "metric": "macro_f1", "labels": LABELS.tolist(),
            "dataset": "sklearn.load_digits", "split_sizes": {k: len(v) for k, v in manifest.items()},
            "data_sha256": hashlib.sha256(x.tobytes() + y.tobytes()).hexdigest(),
            "manifest_sha256": hashlib.sha256((output / "split-manifest.json").read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                        "sklearn": sklearn.__version__, "platform": platform.platform()},
            "interpretation": "Descriptive confirmation exercise; no search winner or confidence claim."}
    save_json(output / "plan.json", plan)
    frozen = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                            check=True, capture_output=True, text=True).stdout
    (output / "resolved-requirements.txt").write_text(frozen, encoding="utf-8")
    if tracking:
        tracking.log_outputs(async_req=False, planned_trials=10, training_epochs=EPOCHS,
                             split_manifest_sha256=plan["manifest_sha256"])

    records = []
    with threadpool_limits(limits=1):
        for seed_index, seed in enumerate(SEEDS, start=1):
            # Alternate order to avoid always timing one candidate first.
            names = list(CANDIDATES) if seed_index % 2 else list(reversed(CANDIDATES))
            for name in names:
                record = {"candidate": name, "alpha": CANDIDATES[name], "seed": seed,
                          "seed_index": seed_index, "status": "running"}
                trial_path = output / f"trial-{name}-{seed}.json"
                save_json(trial_path, record)
                start = time.perf_counter()
                try:
                    model = train(CANDIDATES[name], seed, x_train, y[training])
                    fit_seconds = time.perf_counter() - start
                    predictions = model.predict(x_validation)
                    score = float(f1_score(y[validation], predictions, labels=LABELS,
                                           average="macro", zero_division=0))
                    record.update(status="completed", validation_macro_f1=score,
                                  fit_seconds=fit_seconds, completed_epochs=EPOCHS,
                                  class_report=classification_report(
                                      y[validation], predictions, labels=LABELS,
                                      output_dict=True, zero_division=0))
                    save_json(output / f"predictions-{name}-{seed}.json",
                              {"row_ids": validation.tolist(), "labels": y[validation].tolist(),
                               "predictions": predictions.tolist()})
                except Exception as error:
                    record.update(status="failed", elapsed_seconds=time.perf_counter() - start,
                                  error_type=type(error).__name__, error=str(error))
                records.append(record)
                save_json(trial_path, record)
                print(json.dumps({k: record[k] for k in ("candidate", "seed", "status")}), flush=True)
                if tracking and record["status"] == "completed":
                    tracking.log_metrics(step=seed_index, **{
                        f"{name}_validation_macro_f1": record["validation_macro_f1"],
                        f"{name}_fit_seconds": record["fit_seconds"]})

    summary = summarize(records)
    save_json(output / "summary.json", summary)
    if tracking:
        tracking.log_outputs(async_req=False, panel_status=summary["status"])
        for path in sorted(output.iterdir()):
            tracking.log_file_ref(path=str(path), name=path.name)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
