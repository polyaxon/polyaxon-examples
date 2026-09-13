"""Source-reviewed sandbox benchmark companion; no published measurements.

Creates real Polyaxon services. Run only in an authorized evaluation project.
See the article for measurement boundaries and deployment prerequisites.
"""

import argparse
import hashlib
import json
import math
import statistics
import time
import uuid
from pathlib import Path

from polyaxon.client import SandboxClient

from lifecycle import make_run_client, stop_and_record, wait_for_running


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--owner")
    parser.add_argument("--component", default="sandbox.yaml")
    parser.add_argument("--fixture", default="task.py")
    parser.add_argument("--mode", choices=["fresh", "reuse"], required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--profile", default="cpu-1-memory-512Mi")
    parser.add_argument("--output-dir", default="benchmark-results")
    parser.add_argument("--track", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 100:
        raise ValueError("repetitions must be between 1 and 100")
    if args.track:
        from polyaxon import tracking
        from polyaxon.schemas import V1ArtifactKind

        tracking.init()
        output = Path(tracking.get_outputs_path("sandbox-benchmark", is_dir=True))
    else:
        output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    trial_file = output / "trials.jsonl"
    # Preserve prior evidence; every invocation needs a fresh output directory/run.
    with trial_file.open("x", encoding="utf-8"):
        pass
    component = Path(args.component).resolve()
    fixture = Path(args.fixture).resolve()
    component_bytes, fixture_bytes = component.read_bytes(), fixture.read_bytes()
    (output / "component.yaml").write_bytes(component_bytes)
    (output / "task.py").write_bytes(fixture_bytes)
    manifest = {
        "mode": args.mode, "profile_label": args.profile,
        "repetitions": args.repetitions,
        "component_sha256": hashlib.sha256(component_bytes).hexdigest(),
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "fixture_revision": "sum-and-state-v1",
        "values": [2, 3, 5],
        "expected_total": 10,
        "cache_state": "not controlled; fresh means a new service, not a cold node",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    records, cleanups = [], []
    client = sandbox = None
    expected_sequence = 0
    started = time.monotonic()

    def release():
        nonlocal client, sandbox, expected_sequence
        if client is not None:
            cleanup_start = time.monotonic()
            receipt = stop_and_record(client, seconds=30, directory=output)
            receipt["cleanup_seconds"] = time.monotonic() - cleanup_start
            cleanups.append(receipt)
            try:
                client.client.close()
            except Exception as error:
                receipt["client_close_error_type"] = type(error).__name__
            finally:
                client = None
        sandbox = None
        expected_sequence = 0

    try:
        for index in range(args.repetitions):
            trial_start = time.monotonic()
            trial_id = uuid.uuid4().hex
            record = {
                "index": index, "trial_id": trial_id, "mode": args.mode,
                "outcome": "execution_error", "phase": "submission",
                "run_uuid": None, "setup_seconds": 0.0,
                "command_seconds": None,
            }
            candidate_client = None
            try:
                if client is None:
                    candidate_client = make_run_client(args.project, owner=args.owner)
                    run = candidate_client.create_from_polyaxonfile(
                        polyaxonfile=str(component), approved=True,
                        tags=[f"benchmark-{trial_id}"],
                    )
                    client = candidate_client
                    record["run_uuid"] = run.uuid
                    record["phase"] = "readiness"
                    wait_for_running(client, seconds=120)
                    sandbox = SandboxClient(
                        owner=client.owner, project=client.project,
                        run_uuid=run.uuid, client=client.client,
                        manual_exceptions_handling=True,
                    )
                    sandbox.ping()
                    record["phase"] = "fixture_upload"
                    sandbox.fs.upload_file(
                        path="/workspace/task.py", local_path=str(fixture), timeout=10,
                    )
                    record["setup_seconds"] = time.monotonic() - trial_start
                record["run_uuid"] = client.run_uuid
                expected_sequence += 1
                record["phase"] = "input_upload"
                input_path = output / f"input-{trial_id}.json"
                input_path.write_text(json.dumps({
                    "trial_id": trial_id, "values": manifest["values"],
                }), encoding="utf-8")
                sandbox.fs.upload_file(
                    path="/workspace/input.json", local_path=str(input_path), timeout=10,
                )
                record["input_bytes"] = input_path.stat().st_size
                record["phase"] = "command"
                command_start = time.monotonic()
                result = sandbox.process.exec(
                    command=["python", "/workspace/task.py"], timeout_ms=5_000,
                )
                record.update(
                    command_seconds=time.monotonic() - command_start,
                    server_duration_ms=result.duration_ms,
                    exit_code=result.exit_code, timed_out=result.timed_out,
                    stdout_truncated=result.stdout_truncated,
                    stderr_truncated=result.stderr_truncated,
                )
                if result.timed_out:
                    record["outcome"] = "command_timeout"
                elif result.exit_code != 0 or result.stdout_truncated or result.stderr_truncated:
                    record["outcome"] = "command_error"
                else:
                    record["phase"] = "download_and_verify"
                    report_path = output / f"report-{trial_id}.json"
                    sandbox.fs.download_file(
                        path="/workspace/report.json", local_path=str(report_path), timeout=10,
                    )
                    observed = json.loads(report_path.read_text(encoding="utf-8"))
                    expected = {"trial_id": trial_id, "total": 10, "sequence": expected_sequence}
                    record["expected_sequence"] = expected_sequence
                    record["outcome"] = "success" if observed == expected else "wrong_result"
                    record["output_bytes"] = report_path.stat().st_size
            except Exception as error:
                record["error_type"] = type(error).__name__
                if client is None and record["phase"] == "submission":
                    record["submission_uncertain"] = True
                    record["reconcile_tag"] = f"benchmark-{trial_id}"
            finally:
                # Submission may have succeeded remotely without returning a UUID.
                # Close the local transport, but do not guess which run to stop.
                if client is None and candidate_client is not None:
                    try:
                        candidate_client.client.close()
                    except Exception as error:
                        record["client_close_error_type"] = type(error).__name__
                record["trial_seconds"] = time.monotonic() - trial_start
                records.append(record)
                with trial_file.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record) + "\n")
                # Do not reuse possibly changed state after an uncertain execution.
                if args.mode == "fresh" or record["outcome"] != "success":
                    release()
            if record.get("submission_uncertain") or any(
                not receipt["confirmed"] or receipt.get("client_close_error_type")
                for receipt in cleanups
            ):
                break  # Reconcile before creating more workloads.
    finally:
        release()
    successes = [r for r in records if r["outcome"] == "success"]
    command_times = [r["command_seconds"] for r in successes]
    wall = time.monotonic() - started
    summary = {
        **manifest,
        "attempted_trials": len(records),
        "unattempted_trials": args.repetitions - len(records),
        "successful_trials": len(successes),
        "failed_trials": len(records) - len(successes),
        "command_timeouts": sum(r.get("timed_out", False) for r in records),
        "command_median_seconds": statistics.median(command_times) if command_times else None,
        "command_p95_seconds": percentile(command_times, 0.95),
        "total_wall_seconds_including_cleanup": wall,
        "wall_seconds_per_success": wall / len(successes) if successes else None,
        "cleanup_receipts": cleanups,
        "unconfirmed_cleanups": sum(not row["confirmed"] for row in cleanups),
        "uncertain_submissions": sum(r.get("submission_uncertain", False) for r in records),
        "client_close_errors": sum("client_close_error_type" in r for r in records)
        + sum("client_close_error_type" in receipt for receipt in cleanups),
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.track:
        tracking.log_inputs(**manifest)
        tracking.log_metrics(
            successful_trials=len(successes), failed_trials=summary["failed_trials"],
            total_wall_seconds=wall,
        )
        for path in [trial_file, summary_path, output / "manifest.json"]:
            tracking.log_artifact_ref(path=str(path), kind=V1ArtifactKind.FILE, name=path.stem)
    print(json.dumps(summary, indent=2))
    complete = (
        len(successes) == args.repetitions
        and not summary["unconfirmed_cleanups"]
        and not summary["client_close_errors"]
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
