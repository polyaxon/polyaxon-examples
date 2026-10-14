# Profile CIFAR-10 training

Companion for `profile-pytorch-training-on-polyaxon`. Source-reviewed October 14, 2026; no training, profiling or throughput runs executed. No measured speedup is supplied.

Requirements: configured Polyaxon CLI/project and a dedicated NVIDIA GPU queue, compatible drivers, four CPUs and 8 GiB host memory per job. The runtime downloads CIFAR-10 and installs a deployment-compatible Polyaxon client plus torchvision 0.22.1 over PyTorch 2.7.1. Package freeze is written to logs. Check dataset usage terms for your setting.

From this directory, upload the source and capture a trace:

```bash
polyaxon run -f polyaxonfile.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=profile -P workers=0
```

Approve if required. Download the run's output artifacts in the UI. Open the exported `trace-5.json` and `trace-10.json` locally in a Chrome-trace-compatible viewer (for example Perfetto). Inspect CUDA tracks together with the named data-fetch/transfer/training scopes. The operator table is sorted by self CPU time; it is not a ranking of GPU bottlenecks.

Capture the same trace with four input workers, then run unprofiled windows for both settings:

```bash
polyaxon run -f polyaxonfile.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=profile -P workers=4
polyaxon run -f polyaxonfile.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=bench -P workers=0
polyaxon run -f polyaxonfile.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=bench -P workers=4
```

Both modes warm up for 20 steps. Profiling records ten steps with two cycles of wait=1, warmup=1, active=3. Benchmarking times 100 batches including input fetching, copies, forward/backward and optimizer; CUDA synchronization brackets the measured window. Downloads, worker startup and initialization precede it. Repeat whole jobs in alternating order on the same GPU type and fixed CPU budget. Compare `samples_per_second` and `run.json`; retain traces as diagnosis artifacts. This short run is a systems workload, not a CIFAR-10 quality claim or a tuned training recipe.
