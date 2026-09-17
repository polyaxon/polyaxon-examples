"""Single-process CPU recovery exercise. Source-reviewed; not a production trainer."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

import torch
from torch import nn


def atomic_save(path, writer):
    """One writer; temporary sibling and final file must share a filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Persist the directory entry on the Linux/macOS filesystems used here.
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def save_json(path, value):
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    atomic_save(path, lambda stream: stream.write(encoded))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/recovery"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interrupt-at-step", type=int, default=0)
    parser.add_argument("--tracked", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1 or args.interrupt_at_step < 0:
        parser.error("epochs must be positive; interrupt-at-step must be nonnegative")

    tracking = None
    output = args.output
    if args.tracked:
        from polyaxon import tracking

        tracking.init()
        output = Path(tracking.get_outputs_path()) / "training-recovery"
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)
    checkpoints = sorted(checkpoint_dir.glob("epoch-*.pt"))
    if args.resume and not checkpoints:
        raise RuntimeError("Resume requested, but no completed checkpoint exists.")
    if not args.resume and checkpoints:
        raise RuntimeError("Checkpoints already exist. Use --resume or a new output directory.")

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(7)
    shuffle = torch.Generator().manual_seed(19)
    # No download, worker prefetch, or random augmentation in this exercise.
    x = torch.linspace(-2, 2, 256 * 4).reshape(256, 4)
    y = x @ torch.tensor([[0.4], [-0.8], [0.2], [0.6]]) + 0.1 * torch.sin(x[:, :1])
    dataset_hash = hashlib.sha256(
        json.dumps({"x": x.tolist(), "y": y.tolist()}, sort_keys=True).encode()
    ).hexdigest()
    config = {"batch_size": 32, "seed": 7, "shuffle_seed": 19,
              "learning_rate": 0.03, "momentum": 0.9,
              "scheduler_step_size": 2, "scheduler_gamma": 0.8,
              "dataset_revision": "synthetic-regression-v1"}
    runtime = {"torch": str(torch.__version__), "python": platform.python_version(),
               "system": platform.system(), "machine": platform.machine()}
    contract = {"schema_version": 1, "config": config, "runtime": runtime,
                "dataset_sha256": dataset_hash,
                "source_sha256": sha256(Path(__file__))}

    model = nn.Sequential(nn.Linear(4, 16), nn.ReLU(), nn.Dropout(0.2), nn.Linear(16, 1))
    optimizer = torch.optim.SGD(model.parameters(), lr=config["learning_rate"],
                               momentum=config["momentum"])
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer, step_size=config["scheduler_step_size"], gamma=config["scheduler_gamma"]
    )
    next_epoch, global_step, history = 0, 0, []
    restored = None
    if args.resume:
        restored = checkpoints[-1]
        # Only load trusted artifacts. A load error is fatal, never a fresh start.
        saved = torch.load(restored, map_location="cpu", weights_only=True)
        if saved["contract"] != contract:
            raise RuntimeError("Checkpoint contract differs: review code, data, config, and runtime.")
        next_epoch, global_step = saved["next_epoch"], saved["global_step"]
        if (next_epoch < 1 or next_epoch > args.epochs
                or global_step != next_epoch * 8
                or restored.name != f"epoch-{next_epoch:04d}.pt"):
            raise RuntimeError("Checkpoint progress is inconsistent with this exercise.")
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        scheduler.load_state_dict(saved["scheduler"])
        history = saved["history"]
        # Construction above can consume randomness; restore it last.
        torch.set_rng_state(saved["torch_rng"])
        shuffle.set_state(saved["shuffle_rng"])
    model.train()

    attempt_id = uuid.uuid4().hex
    attempt_dir = output / "attempts" / attempt_id
    attempt_dir.mkdir(parents=True)
    frozen = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                            check=True, capture_output=True, text=True).stdout
    (attempt_dir / "resolved-requirements.txt").write_text(frozen, encoding="utf-8")
    record = {"attempt_id": attempt_id, "contract": contract,
              "restored_checkpoint": restored.name if restored else None,
              "restored_sha256": sha256(restored) if restored else None,
              "restored_step": global_step, "target_epochs": args.epochs,
              "status": "running"}
    save_json(attempt_dir / "record.json", record)
    print(json.dumps({"attempt_id": attempt_id, "restored_step": global_step,
                      "next_epoch_index": next_epoch}), flush=True)
    if tracking:
        tracking.log_outputs(async_req=False, recovery_attempt=attempt_id,
                             restored_step=global_step,
                             restored_checkpoint=record["restored_checkpoint"] or "none")

    def finish(status, exit_code):
        record.update(status=status, final_step=global_step)
        save_json(attempt_dir / "record.json", record)
        if tracking:
            tracking.log_file_ref(path=str(attempt_dir / "record.json"),
                                  name=f"recovery-attempt-{attempt_id}")
            tracking.log_file_ref(path=str(attempt_dir / "resolved-requirements.txt"),
                                  name=f"recovery-environment-{attempt_id}")
        return exit_code

    # Epoch boundaries deliberately avoid serializing a partially consumed sampler.
    for epoch in range(next_epoch, args.epochs):
        order = torch.randperm(len(x), generator=shuffle)
        total_loss = 0.0
        for indices in order.split(config["batch_size"]):
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.mse_loss(model(x[indices]), y[indices])
            loss.backward()
            optimizer.step()
            global_step += 1
            total_loss += loss.item() * len(indices)
            if args.interrupt_at_step and global_step == args.interrupt_at_step:
                print("Intentional interruption; unfinished epoch is not checkpointed.", flush=True)
                return finish("interrupted", 75)

        scheduler.step()
        row = {"epoch": epoch + 1, "step": global_step,
               "loss": total_loss / len(x), "next_learning_rate": scheduler.get_last_lr()[0]}
        history.append(row)
        checkpoint = checkpoint_dir / f"epoch-{epoch + 1:04d}.pt"
        if checkpoint.exists():
            raise RuntimeError("Refusing to overwrite a completed checkpoint.")
        state = {"contract": contract, "next_epoch": epoch + 1, "global_step": global_step,
                 "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                 "scheduler": scheduler.state_dict(), "torch_rng": torch.get_rng_state(),
                 "shuffle_rng": shuffle.get_state(), "history": history}
        atomic_save(checkpoint, lambda stream: torch.save(state, stream))
        # Logs and metadata follow checkpoint publication. They are not the commit marker.
        print(json.dumps({**row, "checkpoint": checkpoint.name}), flush=True)
        if tracking:
            tracking.log_metrics(step=global_step, train_loss=row["loss"],
                                 next_learning_rate=row["next_learning_rate"])
            tracking.log_file_ref(path=str(checkpoint), name=f"checkpoint-epoch-{epoch + 1}")

    save_json(attempt_dir / "summary.json", {"history": history, "final_step": global_step})
    return finish("completed", 0)


if __name__ == "__main__":
    raise SystemExit(main())
