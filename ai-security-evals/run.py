"""Run the six-case fixture, retain evidence, and propagate the evaluation gate."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-output", type=Path)
    parser.add_argument("--promptfoo", default=str(BASE / "node_modules/.bin/promptfoo"))
    args = parser.parse_args()
    tracking = None
    if args.local_output:
        output_dir = args.local_output.resolve()
    else:
        from polyaxon import tracking
        tracking.init()
        output_dir = Path(tracking.get_outputs_path("promptfoo-report", is_dir=True))
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / "results.json"
    if report.exists():
        raise RuntimeError("Choose a fresh output directory; an old report must not satisfy the gate")

    env = dict(os.environ, PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE="1")
    env.setdefault("PROMPTFOO_CONFIG_DIR", str(output_dir / "state"))
    command = [args.promptfoo, "eval", "-c", str(BASE / "promptfooconfig.yaml"),
               "--no-cache", "--no-write", "--no-progress-bar", "--no-table",
               "-o", str(report)]
    status = {"runner_exit_code": 1, "complete": False, "gate_passed": False}
    try:
        process = subprocess.run(command, cwd=BASE, env=env, timeout=600, check=False)
        status["runner_exit_code"] = process.returncode
        results = json.loads(report.read_text())["results"]
        expected = Counter(case["vars"]["caseId"] for case in
                           json.loads((BASE / "cases.json").read_text()))
        rows = results["results"]
        observed = Counter(row["testCase"]["vars"]["caseId"] for row in rows)
        status["complete"] = bool(expected) and expected == observed
        stats = results["stats"]
        status.update({key: stats[key] for key in ("successes", "failures", "errors")})
        status["gate_passed"] = (process.returncode == 0 and status["complete"]
                                 and all(row.get("success") is True for row in rows)
                                 and stats["failures"] == 0 and stats["errors"] == 0)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        status["execution_error"] = str(error)

    manifest = {
        "example_version": "1.0.0",
        "fixture_mode": env.get("FIXTURE_MODE", "safe"),
        "promptfoo_version": "0.122.2",
        "files_sha256": {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
                         for name in ("cases.json", "fixture-provider.cjs", "promptfooconfig.yaml")},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    if tracking is not None:
        for name in ("results.json", "manifest.json", "status.json"):
            path = output_dir / name
            if path.exists():
                tracking.log_artifact_ref(name=name, path=str(path))
        tracking.log_metrics(
            gate_passed=int(status["gate_passed"]),
            complete=int(status["complete"]),
            **{key: status[key] for key in ("successes", "failures", "errors") if key in status},
        )
    print(json.dumps(status, indent=2))
    return 0 if status["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
