"""Prepare and audit illustrative row-wise and grouped evaluation splits."""

import argparse
from collections import Counter
import csv
import hashlib
from itertools import combinations
import json
from pathlib import Path
import platform
import unicodedata

import sklearn
from sklearn.model_selection import GroupShuffleSplit

from fixture import make_rows

SPLITS = ("train", "validation", "test")
POLICY = "case-or-normalized-text-components-v1"


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def fingerprint(text):
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return sha256(normalized.encode("utf-8"))


def annotate(rows):
    """Join cases connected by identical normalized text; labels are not used."""
    parents = {row["case_id"]: row["case_id"] for row in rows}

    def root(case_id):
        while parents[case_id] != case_id:
            parents[case_id] = parents[parents[case_id]]
            case_id = parents[case_id]
        return case_id

    seen = {}
    for row in rows:
        key = fingerprint(row["text"])
        if key in seen:
            left, right = sorted((root(row["case_id"]), root(seen[key])))
            parents[right] = left
        else:
            seen[key] = row["case_id"]
    return [dict(row, group_id=root(row["case_id"]),
                 fingerprint=fingerprint(row["text"])) for row in rows]


def grouped_assignment(rows, seed):
    groups = [row["group_id"] for row in rows]
    outer = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    development, test = next(outer.split(rows, groups=groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1)
    train_local, validation_local = next(inner.split(
        development, groups=[groups[i] for i in development]
    ))
    indices = {"train": development[train_local],
               "validation": development[validation_local], "test": test}
    return {rows[i]["id"]: name for name, selected in indices.items() for i in selected}


def audit(rows, assignment):
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Row IDs must be unique.")
    if set(assignment) != {row["id"] for row in rows}:
        raise ValueError("Every row must have exactly one split assignment.")
    if set(assignment.values()) != set(SPLITS):
        raise ValueError("All three splits must be nonempty and named correctly.")
    selected = {name: [r for r in rows if assignment[r["id"]] == name] for name in SPLITS}
    overlaps = {}
    for left, right in combinations(SPLITS, 2):
        overlaps[f"{left}:{right}"] = {
            key: len({r[key] for r in selected[left]} & {r[key] for r in selected[right]})
            for key in ("id", "case_id", "group_id", "fingerprint")
        }
    summaries = {
        name: {"rows": len(part), "groups": len({r["group_id"] for r in part}),
               "labels": dict(sorted(Counter(r["label"] for r in part).items()))}
        for name, part in selected.items()
    }
    return {"passed": all(n == 0 for pair in overlaps.values() for n in pair.values()),
            "pairwise_shared_key_counts": overlaps, "splits": summaries}


def prepare(output, seed=23):
    rows = annotate(make_rows())
    # This intentionally bad split sends related views to different partitions.
    # It is a diagnostic control, not a recommended random splitting method.
    rowwise = {row["id"]: SPLITS[i % 3] for i, row in enumerate(rows)}
    grouped = grouped_assignment(rows, seed)
    assignments = {"rowwise": rowwise, "grouped": grouped}
    reports = {name: audit(rows, assignment) for name, assignment in assignments.items()}
    manifests = {
        name: [{key: row[key] for key in ("id", "case_id", "group_id", "fingerprint")}
               | {"split": assignment[row["id"]]} for row in rows]
        for name, assignment in assignments.items()
    }
    record = {
        "dataset_revision": "synthetic-support-v1",
        "dataset_sha256": sha256(canonical_json(rows)),
        "split_policy": POLICY,
        "normalization": "Unicode NFKC, casefold, collapse whitespace; v1",
        "seed": seed,
        "group_fractions": {"train": 0.6, "validation": 0.2, "test": 0.2},
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "source_sha256": {name: sha256(Path(__file__).with_name(name).read_bytes())
                          for name in ("fixture.py", "prepare.py")},
        "manifest_sha256": {name: sha256(canonical_json(value)) for name, value in manifests.items()},
        "limitations": ["Synthetic fixture; not a quality benchmark.",
                        "No semantic duplicate detection, temporal audit, or model training.",
                        "Passing the audit only establishes the listed disjointness checks."],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("record.json", record), ("audit.json", reports)):
        (output / name).write_bytes(canonical_json(value))
    for name, manifest in manifests.items():
        folder = output / name
        folder.mkdir()
        (folder / "manifest.json").write_bytes(canonical_json(manifest))
        for split in SPLITS:
            with (folder / f"{split}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(r for r in rows if assignments[name][r["id"]] == split)
    return record, reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs"))
    parser.add_argument("--seed", type=int, default=23)
    args = parser.parse_args()
    record, reports = prepare(args.output, args.seed)
    print(json.dumps(reports, indent=2))
    if not reports["grouped"]["passed"]:
        raise SystemExit("Grouped audit failed; inspect the saved reports before training.")
