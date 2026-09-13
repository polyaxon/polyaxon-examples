"""Exact-match evaluator companion. Source-reviewed, not execution-verified."""

import argparse
import json
from pathlib import Path

EVALUATOR_REVISION = "exact-match-v2"


def indexed(records, field):
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty case array")
    result = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each case must be an object")
        case_id = record.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("Case IDs must be nonempty strings")
        if not isinstance(record.get(field), str):
            raise ValueError(f"Every case must contain a string {field}")
        if case_id in result:
            raise ValueError("Duplicate case ID")
        result[case_id] = record[field]
    return result


def evaluate(manifest, predictions, candidate_revision, minimum_score):
    report = {
        "candidate_revision": candidate_revision,
        "evaluator_revision": EVALUATOR_REVISION,
        "decision": "invalid_input",
        "accepted": False,
    }
    if not 0 <= minimum_score <= 1:
        raise ValueError("minimum-score must be between zero and one")
    try:
        if not isinstance(manifest, dict) or not isinstance(predictions, dict):
            raise ValueError("Manifest and prediction envelopes must be objects")
        revision = manifest.get("dataset_revision")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("The authoritative manifest needs a dataset revision")
        report["dataset_revision"] = revision
        if predictions.get("candidate_revision") != candidate_revision:
            raise ValueError("Predictions do not identify the selected candidate")
        expected = indexed(manifest.get("cases"), "expected")
        actual = indexed(predictions.get("records"), "actual")
        missing = sorted(expected.keys() - actual.keys())
        unexpected = sorted(actual.keys() - expected.keys())
        report.update(
            expected_cases=len(expected),
            completed_cases=len(expected.keys() & actual.keys()),
            missing_ids=missing,
            unexpected_ids=unexpected,
        )
        if missing or unexpected:
            raise ValueError("Predictions do not exactly cover the manifest")
        # Ground truth comes only from the trusted manifest, never predictions.
        normalize = lambda value: " ".join(value.split()).casefold()
        results = [
            {"id": case_id, "correct": normalize(expected[case_id]) == normalize(actual[case_id])}
            for case_id in expected
        ]
        score = sum(case["correct"] for case in results) / len(results)
        accepted = score >= minimum_score
        report.update(
            decision="accepted" if accepted else "rejected",
            accepted=accepted,
            exact_match=score,
            minimum_score=minimum_score,
            results=results,
        )
        return report, 0 if accepted else 1
    except ValueError as error:
        report["error"] = str(error)
        return report, 2


def load_json(path):
    limit = 1024 * 1024
    with Path(path).open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Fixture exceeds the example's 1 MiB input limit")
    return json.loads(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument("--minimum-score", type=float, default=0.90)
    parser.add_argument("--local-output", help="Write locally without Polyaxon tracking")
    args = parser.parse_args()
    try:
        report, exit_code = evaluate(
            load_json(args.manifest), load_json(args.predictions),
            args.candidate_revision, args.minimum_score,
        )
    except (OSError, ValueError) as error:
        report = {
            "candidate_revision": args.candidate_revision,
            "evaluator_revision": EVALUATOR_REVISION,
            "decision": "invalid_input",
            "accepted": False,
            "error_type": type(error).__name__,
        }
        exit_code = 2
    if args.local_output:
        output = Path(args.local_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    else:
        from polyaxon import tracking
        from polyaxon.schemas import V1ArtifactKind

        tracking.init()
        tracking.log_inputs(
            candidate_revision=args.candidate_revision,
            dataset_revision=report.get("dataset_revision", "unavailable"),
            evaluator_revision=EVALUATOR_REVISION,
        )
        if "exact_match" in report:
            tracking.log_metrics(exact_match=report["exact_match"])
        tracking.log_outputs(
            accepted=report["accepted"], decision=report["decision"],
            expected_cases=report.get("expected_cases", 0),
            completed_cases=report.get("completed_cases", 0),
        )
        output = Path(tracking.get_outputs_path("evaluation/summary.json"))
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        tracking.log_artifact_ref(
            path=str(output), kind=V1ArtifactKind.FILE, name="evaluation-summary"
        )
    print(json.dumps({"decision": report["decision"], "report": str(output)}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
