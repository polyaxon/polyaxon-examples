"""CIFAR-10/ResNet18 trace capture and a separate unprofiled throughput window."""
import argparse
import json
import platform
from pathlib import Path
from time import perf_counter

import torch
from torch import nn
from torch.profiler import ProfilerActivity, profile, record_function, schedule
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

from polyaxon import tracking


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["profile", "bench"], default="profile")
    parser.add_argument("--workers", type=int, choices=[0, 4], default=0)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()
    if args.steps < 1 or args.batch_size < 1:
        parser.error("Use positive steps and batch size.")
    torch.manual_seed(23)
    torch.set_num_threads(1)
    tracking.init()
    try:
        out = Path(tracking.get_outputs_path())
        out.mkdir(parents=True, exist_ok=True)
        dataset = datasets.CIFAR10("/tmp/cifar10", train=True, download=True,
                                  transform=transforms.ToTensor())
        loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True,
                            generator=torch.Generator().manual_seed(23),
                            num_workers=args.workers, pin_memory=True, drop_last=True,
                            persistent_workers=args.workers > 0)
        model = models.resnet18(weights=None)
        model.conv1 = nn.Conv2d(3, 64, 3, stride=1, padding=1, bias=False)
        model.maxpool = nn.Identity()
        model.fc = nn.Linear(model.fc.in_features, 10)
        model = model.cuda().train()
        optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
        criterion = nn.CrossEntropyLoss()
        iterator = iter(loader)

        def step():
            nonlocal iterator
            with record_function("input/next_batch"):
                try:
                    images, targets = next(iterator)
                except StopIteration:
                    iterator = iter(loader)
                    images, targets = next(iterator)
            with record_function("input/to_device"):
                images = images.cuda(non_blocking=True)
                targets = targets.cuda(non_blocking=True)
            with record_function("train/forward_backward"):
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(model(images), targets)
                loss.backward()
            with record_function("train/optimizer"):
                optimizer.step()

        for _ in range(20):
            step()
        torch.cuda.synchronize()
        metadata = {
            **vars(args), "seed": 23, "warmup_steps": 20,
            "torch": torch.__version__, "cuda": torch.version.cuda,
            "python": platform.python_version(), "gpu": torch.cuda.get_device_name(0),
            "dataset": "CIFAR10/train", "input_transform": "ToTensor only",
            "scope": "data fetching, transfer, forward, backward, optimizer",
        }
        if args.mode == "profile":
            def save_trace(profiler):
                path = out / f"trace-{profiler.step_num}.json"
                profiler.export_chrome_trace(str(path))
                (out / f"operators-{profiler.step_num}.txt").write_text(
                    profiler.key_averages().table(sort_by="self_cpu_time_total", row_limit=30)
                )
            with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
                         schedule=schedule(wait=1, warmup=1, active=3, repeat=2),
                         on_trace_ready=save_trace, record_shapes=True,
                         profile_memory=True, with_stack=True) as profiler:
                for _ in range(10):
                    step()
                    profiler.step()
            metadata["profile_steps"] = 10
        else:
            start = perf_counter()
            for _ in range(args.steps):
                step()
            torch.cuda.synchronize()
            seconds = perf_counter() - start
            rate = args.steps * args.batch_size / seconds
            metadata.update(elapsed_seconds=seconds, samples_per_second=rate)
            tracking.log_outputs(async_req=False, samples_per_second=rate)
        (out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    finally:
        tracking.end()


if __name__ == "__main__":
    main()
