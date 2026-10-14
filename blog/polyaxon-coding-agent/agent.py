"""A small, bounded JSON-action coding agent using native Polyaxon sandbox APIs."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
from time import monotonic, sleep

import requests
from polyaxon.client import RunClient, SandboxClient
from polyaxon.schemas import V1Statuses


ACTION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["action", "path", "content"],
    "properties": {
        "action": {"type": "string", "enum": ["read", "write", "check", "finish"]},
        "path": {"type": ["string", "null"]},
        "content": {"type": ["string", "null"]},
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--allow-checks", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("agent-output"))
    args = parser.parse_args()
    if not args.allow_checks:
        parser.error("--allow-checks authorizes execution of the supplied unittest command in the workspace")
    args.out.mkdir(parents=True, exist_ok=False)
    fixture = Path(__file__).resolve().parent
    original = (fixture / "amounts.py").read_text()
    trusted_tests = (fixture / "test_amounts.py").read_bytes()
    sandbox = SandboxClient(owner=args.owner, project=args.project)
    run_client = None
    transcript, checked_hash = [], None
    try:
        run = sandbox.create(name="amount-parser-repair", content={
            "queue": args.queue, "termination": {"timeout": 1800},
            "component": {
                "plugins": {"auth": False, "mountArtifactsStore": False},
                "run": {"kind": "service", "container": {
                    "image": "python:3.12-slim",
                    "resources": {"requests": {"cpu": "1", "memory": "512Mi"},
                                  "limits": {"cpu": "2", "memory": "1Gi"}},
                }},
            },
        })
        run_client = RunClient(owner=args.owner, project=args.project,
                               run_uuid=run.uuid, client=sandbox.client)
        (args.out / "workspace.json").write_text(json.dumps({"run_uuid": run.uuid}) + "\n")
        run_client.approve()
        deadline = monotonic() + 300
        while monotonic() < deadline:
            run_client.refresh_data()
            status = run_client.run_data.status
            if status == V1Statuses.RUNNING:
                break
            if V1Statuses.is_done(status):
                raise RuntimeError(f"Workspace ended: {status}")
            sleep(2)
        else:
            raise TimeoutError("Workspace startup exceeded the polling window.")
        sandbox.ping()
        sandbox.fs.write("/tmp/amounts.py", original)
        sandbox.fs.write("/tmp/test_amounts.py", trusted_tests)
        messages = [{"role": "system", "content": (
            "Repair amounts.py using read, write, check, finish actions. Read the "
            "supplied tests. You may edit only amounts.py. Check runs the trusted "
            "unittest command. Finish is accepted only after successful checks on "
            "the current file. Return exactly one JSON action; use null for unused "
            "path/content. Do not include explanations or markdown."
        )}, {"role": "user", "content": (
            "parse_amount must return decimal.Decimal, accept dollar prefixes, "
            "thousands separators and surrounding whitespace, and raise ValueError "
            "for invalid amounts. Fix the supplied implementation."
        )}]
        succeeded = False
        for turn in range(12):
            response = requests.post(os.environ["SERVICE_URL"].rstrip("/") + "/v1/chat/completions",
                headers={"Authorization": f"token {os.environ['POLYAXON_TOKEN']}"}, timeout=(10, 120),
                json={"model": "coding-agent", "temperature": 0, "max_tokens": 1024,
                      "chat_template_kwargs": {"enable_thinking": False}, "messages": messages,
                      "response_format": {"type": "json_schema", "json_schema": {
                          "name": "coding_action", "schema": ACTION_SCHEMA}}})
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice["finish_reason"] != "stop":
                raise RuntimeError("The model action was incomplete.")
            content = choice["message"]["content"]
            messages.append({"role": "assistant", "content": content})
            try:
                action = json.loads(content)
                name = action["action"]
                if name == "read":
                    if action["path"] not in {"amounts.py", "test_amounts.py"}:
                        raise ValueError("That path is outside the example's read set.")
                    result = {"text": sandbox.fs.read_text("/tmp/" + action["path"], length=8192)}
                elif name == "write":
                    if action["path"] != "amounts.py" or not isinstance(action["content"], str):
                        raise ValueError("Only amounts.py may be written.")
                    if len(action["content"].encode()) > 4096:
                        raise ValueError("The patch exceeds the example's size limit.")
                    sandbox.fs.write("/tmp/amounts.py", action["content"])
                    checked_hash = None
                    result = {"written": "amounts.py"}
                elif name == "check":
                    sandbox.fs.write("/tmp/test_amounts.py", trusted_tests)
                    before = sandbox.fs.read_bytes("/tmp/amounts.py", length=8192)
                    process = sandbox.process.exec(
                        command=["python", "-m", "unittest", "-q", "test_amounts"],
                        workdir="/tmp", timeout_ms=30_000)
                    after = sandbox.fs.read_bytes("/tmp/amounts.py", length=8192)
                    tests_after = sandbox.fs.read_bytes("/tmp/test_amounts.py", length=8192)
                    checked_hash = hashlib.sha256(after).hexdigest() if (
                        before == after and tests_after == trusted_tests
                        and process.exit_code == 0 and not process.timed_out
                    ) else None
                    result = {"exit_code": process.exit_code, "timed_out": process.timed_out,
                              "stdout": (process.stdout or "")[-4000:],
                              "stderr": (process.stderr or "")[-4000:]}
                elif name == "finish":
                    current = sandbox.fs.read_bytes("/tmp/amounts.py", length=8192)
                    if (checked_hash != hashlib.sha256(current).hexdigest()
                        or sandbox.fs.read_bytes("/tmp/test_amounts.py", length=8192) != trusted_tests):
                        raise ValueError("Run successful checks on the current file before finishing.")
                    if current.decode() == original:
                        raise ValueError("No patch was produced.")
                    succeeded, result = True, {"accepted": True}
                else:
                    raise ValueError("Unknown action.")
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                result = {"error": str(error)}
            transcript.append({"turn": turn, "action": content, "result": result})
            messages.append({"role": "user", "content": json.dumps(result)})
            if succeeded:
                break
        current = sandbox.fs.read_text("/tmp/amounts.py", length=8192)
        (args.out / "amounts.py").write_text(current)
        (args.out / "patch.diff").write_text("".join(difflib.unified_diff(
            original.splitlines(keepends=True), current.splitlines(keepends=True),
            fromfile="a/amounts.py", tofile="b/amounts.py")))
        (args.out / "outcome.json").write_text(json.dumps({"accepted": succeeded, "turns": len(transcript),
            "model_revision": "1cfa9a7208912126459214e8b04321603b3df60c"}, indent=2) + "\n")
        if not succeeded:
            raise RuntimeError("No accepted repair within the 12-turn budget.")
    finally:
        (args.out / "actions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in transcript))
        try:
            if run_client is not None:
                run_client.stop()
        finally:
            sandbox.client.close()


if __name__ == "__main__":
    main()
