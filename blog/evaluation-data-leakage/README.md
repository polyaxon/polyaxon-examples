# Evaluation dataset leakage

Companion for the draft Polyaxon article **Prevent data leakage in ML and LLM evaluation datasets**. Article publication is pending. These files were source-reviewed on 2026-09-16; the local example and cluster job have not been executed.

The fixture contains 15 synthetic support cases, three text views of each case, and one reimport with another case ID. It contains no customer data. This is a split-audit demonstration, not a model-quality benchmark. No LLM provider, GPU, or credentials are needed for the local example.

## Run locally

Use Python 3.11+ and run from this directory:

```bash
git clone https://github.com/polyaxon/polyaxon-examples.git
cd polyaxon-examples/blog/evaluation-data-leakage
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python prepare.py --output outputs
python -m pip freeze > outputs/resolved-requirements.txt
```

With an existing checkout, enter `blog/evaluation-data-leakage` directly. Do not clone inside an existing copy. On Windows, use your environment's activation command. The requirements file defines an API compatibility range, not an environment lock; retain the resolved packages and Python version with the results. Reruns need a new output path, such as `--output outputs-second`, because existing reports are never overwritten.

## What the example does

1. Creates a deliberately leaky control by assigning successive related text views to train, validation, and test. This is not a random baseline or a claimed production distribution.
2. Joins rows sharing a case ID or identical normalized text into connected groups. The synthetic reimport connects two case IDs. This toy rule automatically accepts normalized equality; review whether that rule is appropriate before using it on real records.
3. Uses two `GroupShuffleSplit` calls to reserve approximately 20% of groups for test, then 25% of the remainder for validation. With this fixture's 15 connected groups, the intended allocation is nine training groups, three validation groups, and three test groups. Row counts can differ because groups have different sizes.
4. Audits pairwise overlap for row IDs, case IDs, connected group IDs, and normalized text fingerprints. It also records row counts, group counts, and label distributions.
5. Writes both controls' manifests and CSVs, plus hashes, source identities, versions, and audit results. A failed grouped audit returns a nonzero exit code after retaining its evidence. The intentionally leaky control does not make the command fail.

`outputs/audit.json` contains the comparison. `outputs/record.json` identifies the data, policy, source, environment, and serialized manifest hashes. `outputs/grouped/manifest.json` is the assignment to retain across candidate experiments. The grouped CSV files are inputs for your trainer and evaluator; this companion does not train a model or report accuracy.

The expected outcome from source inspection is that the row-wise control reports overlap and the grouped assignment passes the defined disjointness checks. These are expectations, not observed execution results. A passing audit does not establish semantic independence, representativeness, temporal correctness, or absence of foundation-model pretraining contamination. NFKC/case/whitespace normalization does not detect arbitrary paraphrases. Hashes identify content; they do not anonymize it.

Real evaluation datasets need an access boundary around held-out labels. This public synthetic fixture keeps every split readable for teaching. Do not copy that permission model to a private final benchmark. Do not repeatedly change the seed based on model scores. Decide class-coverage and group-size requirements before splitting, then freeze the approved assignment.

## Run the audit as a Polyaxon job

Use a configured Polyaxon CLI/project and an artifact store. The job uses the standard `python:3.12-slim` image and installs its dependencies at startup. The cluster needs access to that image and to PyPI or your configured package mirror.

From this companion directory, submit:

```bash
polyaxon run -f polyaxonfile.yaml -u
```

The `-u/--upload` flag packages this local folder and uploads it under the run's `uploads` directory before the job starts. The container uses that directory as its working directory. The included `.polyaxonignore` excludes local virtual environments, Python caches, and previous output directories.

The container runs `python -m pip install --no-cache-dir -r requirements.txt` before starting the tracked audit. That file includes both scikit-learn and Polyaxon. Installation failure stops the job. Each run includes dependency download/install time. The default SDK requirement resolves the current package version; if your deployment requires a specific SDK version, pin the `polyaxon` entry in `requirements.txt` to that supported version.

The tracked runner saves `resolved-requirements.txt` alongside its other reports. For repeatable comparisons, use those reviewed exact versions as the installation requirements (including the SDK), and pin the base image digest. Recording resolved versions explains a run; it does not by itself make a later installation identical.

The job runs `tracked.py`, which calls the same preparation code under the run's outputs directory. It logs dataset and split identities, audit status, row counts, and references to files it has already written. Polyaxon retains and compares that evidence; the Python program defines the grouping and audit rules. No training job is submitted automatically.

The process exits after writing the artifacts. Review the run before deleting it. Local reports and the virtual environment can be removed when no longer needed; preserve the manifest and environment record if you need to reproduce or compare an experiment.
