# Invoice fields with Qwen2.5-VL on Polyaxon

Companion for `extract-invoice-fields-with-qwen-vl-on-polyaxon`. Source-reviewed October 14, 2026; no model requests or evaluation runs executed. The supplied invoice and labels are synthetic input fixtures. No measured accuracy is supplied.

Requirements: a configured Polyaxon project/CLI, permission to create services, a GPU queue with NVIDIA drivers compatible with the pinned vLLM image, and sufficient GPU/host memory for Qwen2.5-VL-7B and image processing. The node needs Hugging Face access. Start on a dedicated 40 GiB or larger GPU and inspect startup capacity; this is a conservative starting configuration, not a verified fit guarantee. The local client needs Python 3.11+.

```bash
python -m pip install -r requirements.txt
polyaxon run -f service.yaml -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE
```

Approve the service if the project requires approval. Once healthy, retain its run UUID and obtain its externally reachable URL:

```bash
polyaxon ops service -p YOUR_PROJECT -uid SERVICE_UUID --external --url
export SERVICE_URL='PASTE_THE_RETURNED_URL'
export POLYAXON_TOKEN='YOUR_CONFIGURED_POLYAXON_TOKEN'
python extract.py demo-invoice.png --out extraction.json
python evaluate.py demo.jsonl --out demo-evaluation
```

Keep any URL path prefix. Credentials belong in the client environment, not the image or fixture. `demo-evaluation/cases.jsonl` retains field predictions, labels, image hashes and request outcomes. `summary.json` includes exact-document accuracy, supported-field accuracy/coverage and failures. Failures remain in denominators. The one-document demo only exercises the interface; prepare a separate licensed, reviewed, held-out manifest for evaluation. Every label must follow the canonical currency/amount contract in `extract.py`.

Review the saved prediction against the image. Valid JSON establishes format, not field correctness. PDFs must be rendered to page images before using this single-image example; multi-page association and document routing are outside its scope.

Stop when finished:

```bash
polyaxon ops stop -p YOUR_PROJECT -uid SERVICE_UUID
```

The service also has a two-hour termination timeout. Record the companion Git commit, service configuration/run UUID, exact model revision, image digest, labels, prompts and image preprocessing alongside results. The runtime is pinned to vLLM v0.11.2, not presented as the latest release.
