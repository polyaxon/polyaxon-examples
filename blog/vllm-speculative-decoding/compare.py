import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("baseline", type=Path)
parser.add_argument("candidate", type=Path)
args = parser.parse_args()


def load(directory):
    summary = json.loads((directory / "summary.json").read_text())
    rows = [json.loads(line) for line in (directory / "requests.jsonl").read_text().splitlines()]
    keyed = {(row["case_id"], row["repeat"]): row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError("Duplicate request identity.")
    return summary, keyed


baseline, a = load(args.baseline)
candidate, b = load(args.candidate)
for key in ["concurrency", "prompts_sha256", "model_revision", "requests"]:
    if baseline[key] != candidate[key]:
        raise ValueError(f"Incomparable {key}.")
if a.keys() != b.keys():
    raise ValueError("Request inventories differ.")
both = [key for key in a if a[key]["ok"] and b[key]["ok"]]
mismatches = [key for key in both if a[key]["text"] != b[key]["text"]]
print(json.dumps({"requests": len(a), "successful_in_both": len(both),
                  "exact_text_mismatches": len(mismatches),
                  "mismatch_examples": mismatches[:10],
                  "baseline": baseline, "candidate": candidate}, indent=2))
