"""Run inside the supplied Polyaxon job; write evidence before logging references."""

from pathlib import Path
import subprocess
import sys

from polyaxon import tracking

from prepare import prepare


if __name__ == "__main__":
    tracking.init()
    output = Path(tracking.get_outputs_path()) / "split-audit"
    record, reports = prepare(output)
    dependencies = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True, capture_output=True, text=True,
    )
    (output / "resolved-requirements.txt").write_text(dependencies.stdout, encoding="utf-8")
    tracking.log_outputs(
        async_req=False,
        dataset_revision=record["dataset_revision"],
        dataset_sha256=record["dataset_sha256"],
        split_policy=record["split_policy"],
        split_manifest_sha256=record["manifest_sha256"]["grouped"],
        split_seed=record["seed"],
        grouped_audit_passed=reports["grouped"]["passed"],
    )
    tracking.log_metrics(
        step=0,
        grouped_train_rows=reports["grouped"]["splits"]["train"]["rows"],
        grouped_validation_rows=reports["grouped"]["splits"]["validation"]["rows"],
        grouped_test_rows=reports["grouped"]["splits"]["test"]["rows"],
    )
    for relative in ("record.json", "audit.json", "grouped/manifest.json", "resolved-requirements.txt"):
        tracking.log_file_ref(path=str(output / relative), name=relative.replace("/", "-"))
    if not reports["grouped"]["passed"]:
        raise SystemExit("Grouped audit failed; review the run artifacts before training.")
