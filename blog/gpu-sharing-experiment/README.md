# Measure MIG and time-slicing under co-load

Companion for `measure-mig-and-time-slicing-under-co-load`. Source-reviewed October 14, 2026; no cluster configuration changes, workloads or measurements executed. No throughput, latency or fairness result is supplied.

This protocol assumes administrator-prepared benchmark nodes with **exactly one NVIDIA A100 80 GB physical GPU per node**, identical host/driver/software configurations and synchronized host time. One node exposes the whole GPU; a second uses seven homogeneous `1g.10gb` MIG instances and NVIDIA device-plugin single strategy; a third advertises seven time-sliced replicas with `renameByDefault: false`. Under these particular configurations all jobs request `nvidia.com/gpu: 1`, but the allocation units differ. The workload code does not enable MIG, alter plugin settings or change GPU ownership.

Requirements: configured Polyaxon project/CLI, a queue/agent that admits every worker concurrently, at least two CPUs and 4 GiB host memory per worker, compatible drivers, internet access for package installation and a writable shared POSIX filesystem. Configure a volume-claim connection named `gpu-benchmark-sync` mounted at `/mnt/benchmark-sync` in the compute agent's namespace. An artifact-store URL is not a shared barrier directory. Use idle nodes; verify device assignment before interpreting results.

For a seven-worker homogeneous training cohort on the MIG node, from this directory:

```bash
EXPERIMENT_ID=$(uuidgen)
for REPLICA in 0 1 2 3 4 5 6; do
  polyaxon run -f polyaxonfile.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P experiment="$EXPERIMENT_ID" -P node_name=YOUR_MIG_NODE -P mode=mig -P replica="$REPLICA" -P count=7 -P workload=train
done
```

Approve runs if required; all must be admitted together. Use a fresh ID for each group. Run count 1 on the exclusive node; counts 1, 4 and 7 on MIG and time-slicing nodes. A whole-GPU baseline with seven exclusive jobs cannot run concurrently on the one-GPU node. Collect separate solo training and inference baselines. For a mixed group, use one inference worker and six training workers; change `workload` for replica zero before submission. Start with homogeneous runs to confirm the protocol.

Every worker creates a ResNet18 with resident synthetic inputs, warms up 20 batches, writes its ready record and waits for the shared start. Replica zero releases the group five seconds after all ready records exist. Late starts, contract disagreement and missing peers fail the cohort. Each worker uses one CUDA process and times synchronized batches for 45 seconds; no input loading or HTTP server is measured. Outputs are written after timing.

Download each run's `worker.json` and `batches.jsonl` into distinct folders using the UI. Aggregate the complete cohort:

```bash
python summarize.py downloaded/worker-0 downloaded/worker-1 downloaded/worker-2 downloaded/worker-3 downloaded/worker-4 downloaded/worker-5 downloaded/worker-6 --out mig-training-seven.json
```

Only complete batches inside the workers' common active interval contribute. The helper requires every replica and at least 80% overlap. It preserves per-worker rates and p50/p99 batch times, grouping training and inference rates separately. Run whole cohorts repeatedly with fresh IDs. CPU pressure, power/thermal behavior and scheduling remain possible confounders; compare their records, not only GPU utilization. Keep device/plugin configuration, physical GPU identity and all Polyaxon run UUIDs alongside results.

MIG partitions memory/compute resources; time-slicing shares access without equivalent memory/fault isolation. It allocates time per GPU process, so keep process counts fixed. The example's latency is batch execution latency, not a production HTTP p99 estimate. It does not measure fault containment. Remove only your experiment's barrier directory after every worker has stopped, according to your storage policy.
