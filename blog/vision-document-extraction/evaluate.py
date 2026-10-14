"""Score every labeled document; failed requests remain in the denominator."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from extract import Invoice, extract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("evaluation"))
    args = parser.parse_args()
    raw_manifest = args.manifest.read_bytes()
    cases = [json.loads(line) for line in raw_manifest.decode().splitlines() if line.strip()]
    ids = [case["id"] for case in cases]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Supply a nonempty manifest with unique case IDs.")
    args.out.mkdir(parents=True, exist_ok=False)
    fields = list(Invoice.model_fields)
    exact_documents = supported = extracted = supported_correct = failures = 0
    rows = []
    for case in cases:
        truth = Invoice.model_validate(case["expected"]).model_dump()
        supported += sum(truth[key] is not None for key in fields)
        row = {"id": case["id"], "expected": truth}
        try:
            result = extract(args.manifest.parent / case["image"],
                             os.environ["SERVICE_URL"], os.environ["POLYAXON_TOKEN"])
            prediction = result["prediction"]
            row.update(result)
            exact_documents += prediction == truth
            extracted += sum(truth[key] is not None and prediction[key] is not None for key in fields)
            supported_correct += sum(truth[key] is not None and prediction[key] == truth[key] for key in fields)
        except Exception as error:
            failures += 1
            row["error_type"] = type(error).__name__
        rows.append(row)
    (args.out / "cases.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary = {
        "documents": len(cases), "failed_documents": failures,
        "exact_document_rate": exact_documents / len(cases),
        "supported_field_accuracy": supported_correct / supported if supported else None,
        "supported_field_coverage": extracted / supported if supported else None,
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
