# Hyperparameter confirmation across training seeds

Companion for **Did you find better hyperparameters—or a lucky seed?**
Intended article: https://polyaxon.com/blog/compare-hyperparameters-across-seeds/

Source-reviewed only. No training, analysis, cluster execution, tests, or builds were run while
preparing this example. No metric values or winning configuration are asserted.

## Local study

Requires Python 3.12 and the supplied requirements. The digits dataset is bundled with scikit-learn;
no separate data download, external model, or GPU is needed.

```bash
git clone https://github.com/polyaxon/polyaxon-examples.git
cd polyaxon-examples/blog/hyperparameter-seeds
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python study.py --output outputs/seed-study
```

The output directory must be empty. Reusing it is an error. The default local command runs two fixed SGD recipes
over five training seeds, for ten fits at 40 full passes each. It compares alpha=0.0001 (A) with
alpha=0.01 (B), using constant eta0=0.01, log loss, and L2 regularization. These are teaching values,
not settings selected by a completed search. Each trial creates a fresh model and a fresh shuffle
generator. For each seed, A and B receive the same explicitly generated training permutations.
Candidate execution order alternates between seed blocks, and native thread pools are limited to one.

The split is fixed across the panel: stratified test allocation 20% with split seed 101, followed
by a 25% validation allocation from development data with split seed 202. The scaler fits training
rows only. The reserved test partition is never scored by this script. Stratification is a teaching
choice for these rows, not a substitute for group/time separation in a real application.

## Inspect the evidence

- `plan.json`: settings, seeds, source/data/split hashes, runtime, and split counts.
- `split-manifest.json`: exact dataset row assignments, including the reserved test indices.
- `trial-<candidate>-<seed>.json`: status, macro F1, class report, completed epochs, and fit time.
- `predictions-<candidate>-<seed>.json`: validation row IDs, labels, and predictions.
- `summary.json`: each candidate's mean, sample standard deviation, range, and paired B-minus-A
  differences. Positive differences favor B. Win/tie counts are descriptive, not significance tests.
- `resolved-requirements.txt`: installed package snapshot; pin reviewed versions and the base image
  digest before a reproducibility-sensitive or long-running study.

Ordinary per-trial exceptions are retained as failures. If any trial fails, the summary is marked
incomplete, no finalist comparison is produced, and the process exits nonzero. A forced process
kill can leave a record marked running or an unfinished file and no summary. The example does not
automatically retry or merge interrupted studies. Keep that evidence; fix the cause and record a new
complete panel in a separate directory. Do not silently discard failures or keep only favorable retries.

Reported fit time covers model construction and the training loop, excluding data preparation,
evaluation, file writes, dependency installation, and scheduling. It is not GPU-hours or a billing
estimate. The two candidates receive the same number of passes, not a guaranteed identical cost.

Five seeds demonstrate the workflow; they do not establish that five repetitions suffice. Sample
standard deviation describes between-training-seed spread on this split, not a confidence interval
for future production performance. The script does not perform an initial search, infer statistical
significance, choose a winning configuration, save a deployable model, or evaluate the final test set.
Predeclare a practically meaningful improvement, unacceptable class regressions, and a resource
budget for your application. Freeze the selected recipe and deployment seed/checkpoint rule before
separate final evaluation; do not pick whichever seed achieved the highest validation score.

## Polyaxon

Use a configured CLI, an existing project, and an artifact store. Workers need image and package-index
access. Upload this entire directory; `.polyaxonignore` excludes local environments and results.

```bash
polyaxon run -p quick-start -f polyaxonfile.yaml -u
```

Replace `quick-start` with your project. Requirements, including `polyaxon`, install at startup.
The Polyaxonfile uses `matrix.kind: random`, `numRuns: 6`, `concurrency: 2`, and search seed 19.
It samples six alpha values from eight choices: 0.00001, 0.00003, 0.0001, 0.0003, 0.001, 0.003,
0.01, and 0.03. Each child invokes `study.py --tracked --alpha <sampled-value>` and runs the SAME
five training seeds sequentially. This is six configuration-level child runs and 30 fits, not ten
fits in one job and not a randomly sampled training-seed dimension. A retry repeats the child panel.

Per-seed metrics are `sampled_validation_macro_f1` and `sampled_fit_seconds`, logged at seed index
1–5. Complete children also log `validation_macro_f1_mean`, `validation_macro_f1_sd`, and
`fit_seconds_mean` for the comparison dashboard. A failed panel emits no aggregate score. Reports
are saved under each child's `tracking.get_outputs_path()/seed-study` before file references are
logged. Reference logging records lineage, not an independent remote-durability guarantee.

Download two completed configurations using CHILD UUIDs, into fresh local destinations:

```bash
RUN_A="replace-with-first-child-uuid"
RUN_B="replace-with-second-child-uuid"
polyaxon ops artifacts -p quick-start -uid "$RUN_A" --dir outputs/seed-study --path-to outputs/child-a
polyaxon ops artifacts -p quick-start -uid "$RUN_B" --dir outputs/seed-study --path-to outputs/child-b
python compare_panels.py outputs/child-a outputs/child-b > outputs/paired-comparison.json
```

The helper finds exactly one `plan.json` recursively under each download root. It rejects differences
in code, runtime, data/split, metric, training budget/settings, or seed panel. Each configuration must
have one completed trial per seed; missing, duplicate, failed, or nonfinite results are not discarded.
It labels the first configuration A and the second B and produces paired B-minus-A summaries.

Review every search child, including failures, before selecting a shortlist. Comparing selected
search panels is not independent confirmation. Rerun frozen finalists on fresh seeds, using the
actual selected alpha values in place of the illustrative values here:

```bash
python study.py --alpha-a 0.0001 --alpha-b 0.01 --seeds 83 97 109 127 149 --output outputs/confirmation
```

This adds ten fits, for 40 total search-and-confirmation fits before final release training/evaluation.
`--seeds` accepts at least two distinct unsigned 32-bit seeds. `--alpha` selects single-configuration
mode; without it, `--alpha-a` and `--alpha-b` define the local pair. The reserved test stays unevaluated.

## Cleanup

The local command writes only the selected output directory. Matrix children terminate after their
panels; they create no service or PVC. If needed, stop the search with its parent UUID:

```bash
polyaxon ops stop -p quick-start -uid YOUR_MATRIX_RUN_UUID
```

Retain the plan, trial records, and summary for review, then remove local results or apply your normal
run-artifact retention policy. No cleanup command is executed by the example.
