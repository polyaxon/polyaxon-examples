"""One CUDA process per Pod; a shared POSIX barrier precedes timed batches."""
import argparse
import json
import os
from pathlib import Path
from time import perf_counter, sleep, time

import torch
from torchvision import models
from polyaxon import tracking


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--experiment", required=True)
    p.add_argument("--mode", choices=["exclusive", "mig", "timeslice"], required=True)
    p.add_argument("--replica", type=int, required=True)
    p.add_argument("--count", type=int, choices=[1, 4, 7], required=True)
    p.add_argument("--workload", choices=["train", "infer"], default="train")
    p.add_argument("--seconds", type=int, default=45)
    p.add_argument("--sync-root", type=Path, default=Path("/mnt/benchmark-sync"))
    a = p.parse_args()
    if not 0 <= a.replica < a.count or a.seconds < 10:
        p.error("Use a valid replica index and at least ten seconds.")
    if not a.experiment.replace("-", "").isalnum():
        p.error("Use a fresh alphanumeric experiment ID, optionally containing hyphens.")
    torch.manual_seed(23)
    torch.set_num_threads(1)
    tracking.init()
    try:
        out = Path(tracking.get_outputs_path())
        out.mkdir(parents=True, exist_ok=True)
        group = a.sync_root / a.experiment
        group.mkdir(exist_ok=True)
        ready = group / f"ready-{a.replica}.json"
        if ready.exists():
            raise RuntimeError("Stale barrier: use a new experiment ID for every cohort.")
        model = models.resnet18(weights=None).cuda()
        model.train(a.workload == "train")
        images = torch.randn(32, 3, 224, 224, device="cuda")
        targets = torch.randint(1000, (32,), device="cuda")
        optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

        def batch():
            if a.workload == "train":
                optimizer.zero_grad(set_to_none=True)
                torch.nn.functional.cross_entropy(model(images), targets).backward()
                optimizer.step()
            else:
                with torch.inference_mode():
                    model(images)
            torch.cuda.synchronize()

        for _ in range(20):
            batch()
        contract = {"count": a.count, "mode": a.mode, "seconds": a.seconds,
                    "node": os.environ["BENCH_NODE"]}
        atomic_json(ready, {**contract, "replica": a.replica, "workload": a.workload})
        deadline = time() + 300
        go = group / "go.json"
        if a.replica == 0:
            while time() < deadline:
                paths = [group / f"ready-{i}.json" for i in range(a.count)]
                if all(path.exists() for path in paths):
                    peers = [json.loads(path.read_text()) for path in paths]
                    if any(any(row[key] != value for key, value in contract.items()) for row in peers):
                        raise RuntimeError("Workers disagree about the cohort contract.")
                    atomic_json(go, {"start": time() + 5})
                    break
                sleep(0.1)
            else:
                raise TimeoutError("Not every replica reached the barrier.")
        while not go.exists():
            if time() >= deadline:
                raise TimeoutError("No shared start signal.")
            sleep(0.1)
        planned = json.loads(go.read_text())["start"]
        sleep(max(0, planned - time()))
        started = time()
        if started - planned > 1:
            raise RuntimeError("Start lag exceeds one second; discard this cohort.")
        end = perf_counter() + a.seconds
        rows = []
        while perf_counter() < end:
            wall_start, tick = time(), perf_counter()
            batch()
            latency = perf_counter() - tick
            rows.append({"start": wall_start, "end": time(), "seconds": latency, "samples": 32})
        finished = time()
        metadata = {**contract, "experiment": a.experiment, "replica": a.replica,
                    "workload": a.workload, "started": started, "finished": finished,
                    "planned_start": planned, "torch": torch.__version__,
                    "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(0),
                    "visible_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
                    "scope": "synthetic resident inputs; synchronized ResNet18 batches; one CUDA process"}
        (out / "batches.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (out / "worker.json").write_text(json.dumps(metadata, indent=2) + "\n")
    finally:
        tracking.end()


if __name__ == "__main__":
    main()
