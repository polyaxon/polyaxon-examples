"""Client-observed streaming timing. A chunk is not assumed to be one token."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import random
import statistics
from pathlib import Path
from time import perf_counter

import requests


def request(case, repeat, base_url, token):
    row = {"case_id": case["id"], "family": case["family"], "repeat": repeat}
    payload = {
        "model": "qwen-study", "temperature": 0, "max_tokens": 128,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": True, "stream_options": {"include_usage": True},
        "messages": [{"role": "user", "content": case["prompt"]}],
    }
    start = perf_counter()
    first = None
    pieces, usage, finish, done = [], None, None, False
    try:
        with requests.post(base_url.rstrip("/") + "/v1/chat/completions",
                           headers={"Authorization": f"token {token}"},
                           json=payload, stream=True, timeout=(10, 300)) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                event = json.loads(data)
                if event.get("error"):
                    raise RuntimeError("The server returned a streaming error.")
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices", []):
                    text = choice.get("delta", {}).get("content") or ""
                    if text:
                        if first is None:
                            first = perf_counter()
                        pieces.append(text)
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
        end = perf_counter()
        if not done or not usage or first is None or finish not in {"stop", "length"}:
            raise RuntimeError("Incomplete stream or missing timing/token usage.")
        tokens = int(usage["completion_tokens"])
        row.update(ok=True, ttft_seconds=first-start, e2e_seconds=end-start,
                   completion_tokens=tokens, finish_reason=finish,
                   text="".join(pieces),
                   decode_seconds_per_token=(end-first)/(tokens-1) if tokens > 1 else None)
    except Exception as error:
        row.update(ok=False, error_type=type(error).__name__, e2e_seconds=perf_counter()-start)
    return row


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*fraction
    low = int(position)
    high = min(low+1, len(ordered)-1)
    return ordered[low] + (ordered[high]-ordered[low])*(position-low)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", type=Path, default=Path("prompts.jsonl"))
    parser.add_argument("--concurrency", type=int, choices=[1, 4, 8], default=1)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--service-run", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    raw = args.prompts.read_bytes()
    cases = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Supply nonempty prompts with unique IDs.")
    base_url, token = os.environ["SERVICE_URL"], os.environ["POLYAXON_TOKEN"]
    for case in cases:
        warmup = request(case, -1, base_url, token)
        if not warmup["ok"]:
            raise RuntimeError(f"Warmup failed for {case['id']}: {warmup['error_type']}")
    jobs = [(case, repeat) for repeat in range(args.repeats) for case in cases]
    random.Random(19).shuffle(jobs)
    args.out.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(request, case, repeat, base_url, token) for case, repeat in jobs]
        rows = [future.result() for future in concurrent.futures.as_completed(futures)]
    seconds = perf_counter()-start
    rows.sort(key=lambda row: (row["case_id"], row["repeat"]))
    (args.out / "requests.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    good = [row for row in rows if row["ok"]]
    summary = {
        "requests": len(rows), "failed_requests": len(rows)-len(good),
        "concurrency": args.concurrency, "elapsed_seconds": seconds,
        "completed_output_tokens_per_second": sum(row["completion_tokens"] for row in good)/seconds,
        "ttft_p50_seconds": percentile([row["ttft_seconds"] for row in good], 0.5),
        "ttft_p95_seconds": percentile([row["ttft_seconds"] for row in good], 0.95),
        "e2e_p95_seconds": percentile([row["e2e_seconds"] for row in good], 0.95),
        "mean_decode_seconds_per_token": statistics.mean(
            row["decode_seconds_per_token"] for row in good if row["decode_seconds_per_token"] is not None
        ) if any(row["decode_seconds_per_token"] is not None for row in good) else None,
        "service_run_uuid": args.service_run, "prompts_sha256": hashlib.sha256(raw).hexdigest(),
        "model_revision": "1cfa9a7208912126459214e8b04321603b3df60c",
        "python": platform.python_version(), "requests_version": requests.__version__,
        "scope": "closed-loop client-observed timing; decode estimate includes stream completion overhead",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
