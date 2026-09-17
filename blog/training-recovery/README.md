# Training recovery

Companion for the draft Polyaxon article **Resume interrupted training without losing progress**.
Source-reviewed only: no training, recovery, comparison, or cluster execution has been performed.

## Scope

A single-process CPU PyTorch exercise on synthetic regression data. It checkpoints all state used
by this loop at epoch boundaries: model, SGD momentum, scheduler, CPU RNG, shuffle generator,
completed progress, and metric history. It records source/data hashes and runtime/configuration.
It has no data download, GPU, AMP, worker prefetch, streaming input, or distributed shards.

Python 3.12 and a POSIX filesystem supporting file and directory fsync are required.
Use one writer per output directory. Checkpoints are trusted local or operator-controlled artifacts;
`weights_only=True` does not make arbitrary downloaded files safe to trust.

## Local exercise

```bash
git clone https://github.com/polyaxon/polyaxon-examples.git
cd polyaxon-examples/blog/training-recovery
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python train.py --output outputs/recovery --interrupt-at-step 27
```

The last command deliberately exits with code 75 after three updates in epoch 4. Run the next
command separately; chaining with `&&` would skip it because the first process exits nonzero.

```bash
python train.py --output outputs/recovery --resume
```

By construction there are eight batches per epoch: the completed checkpoint is epoch 3 / step 24,
and the replacement process repeats epoch 4 before continuing to epoch 8 / step 64. These are
expected control-flow values, not measured results. `attempts/<id>/record.json` records restored
checkpoint/hash/step and the final step/status; a completed attempt also has `summary.json`.
An abrupt external kill may leave the attempt record marked running; the checkpoint remains the
recovery authority. The deliberately interrupted process exits normally through Python; this does
not demonstrate node-loss durability or a kill during serialization.

To produce an uninterrupted baseline for comparison, use the SAME environment and source:

```bash
python train.py --output outputs/baseline
```

Compare the state tensors and full histories in the final `epoch-0008.pt` files, rather than the
serialized file bytes. A completed final step alone is insufficient. Across hardware or software
changes, bitwise equivalence is not promised. No comparison has been executed for this draft.

## Checkpoint publication and restore policy

Each checkpoint is written to a unique temporary sibling, flushed/fsynced, then renamed to a
completed `epoch-NNNN.pt` file, followed by a directory fsync. Temporary `.tmp` files never match
the loader's glob. This requires the filesystem semantics above; it is not an object-store commit
protocol. All generations are retained for this tiny example. Production jobs need a retention
policy and confirmation of durable remote upload before deleting older recoverable generations.

`--resume` selects the latest completed filename and fails if none exists. A corrupt or incompatible
completed checkpoint is an error, never a reason to start from zero or silently fall back. Restore
an operator-verified earlier checkpoint into a separate recovery directory if you need rollback.
For this demonstration, the file's epoch, step, and name must agree. Reusing a directory without
`--resume` also fails. There is no concurrent-writer lock; the single-writer prerequisite matters.

The checkpoint contract rejects differences in training source, data, configuration, Python patch
version, PyTorch version, OS, or architecture. It does not capture every property of a machine or
the full dependency graph. The dependency snapshot supplements that record. The target epoch
count and interruption setting can change without changing the training contract.

## Polyaxon exercise

Requires a configured CLI/deployment, an existing project, package-index access, and an artifact
store that survives the failure under study. The image installs `requirements.txt`, including
`polyaxon`, at startup. Pin reviewed dependency versions and the base image digest for longer jobs;
the floating starter environment can change between attempts, in which case restoration rejects
the recorded runtime mismatch.

The included `.polyaxonignore` keeps local environments and outputs out of the folder upload.
Keep it in the repository even if your global Git ignore file requires explicitly adding it.

```bash
polyaxon run -p quick-start -f polyaxonfile.yaml -u
```

Replace `quick-start` with your existing project. Capture the returned run UUID. Once the intentional
failure is terminal, confirm `outputs/training-recovery/checkpoints/epoch-0003.pt` is available
in the artifact store, then use the existing run's UUID:

```bash
RUN_UUID="replace-with-the-interrupted-run-uuid"
polyaxon ops resume -p quick-start -uid "$RUN_UUID" -f resume.yaml
```

The preset explicitly enables application restoration and disables the deliberate interruption.
Polyaxon restores available run artifacts; Python restores the state dictionaries. Files are saved
under `tracking.get_outputs_path()`. `log_file_ref` records lineage, not a remote upload guarantee.
Local rename completion cannot prove a cloud artifact synchronization finished before node loss.

To preserve the original run and continue from copied artifacts instead, use this as an ALTERNATIVE
after the original run is terminal (do not run both variants concurrently):

```bash
polyaxon ops restart -p quick-start -uid "$RUN_UUID" --copy -f resume.yaml
```

A plain restart does not select artifact copying. A resumed attempt may append to the same run's
history; attempt JSON files distinguish restored progress from the original execution. Use the new
UUID returned by a copy/restart for subsequent operations on that run.

## Cleanup

Local commands create only the chosen `outputs/` directory. The cluster job should terminate after
the deliberate failure or the final epoch. If needed, stop the active job explicitly:

```bash
polyaxon ops stop -p quick-start -uid "$RUN_UUID"
```

Retain the checkpoint and attempt records until the recovery review is complete, then remove the
local output directory or delete run artifacts through your normal retention process. No service,
PVC, or cluster is provisioned by this example.
