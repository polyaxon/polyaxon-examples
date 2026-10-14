# Benchmark prompt-lookup speculative decoding

Companion for `benchmark-vllm-speculative-decoding-on-polyaxon`. Source-reviewed October 14, 2026; no serving or benchmark runs executed. No latency/speedup measurements are supplied.

Requirements: configured Polyaxon CLI/project, service permissions, a dedicated NVIDIA GPU queue and compatible drivers. The node downloads pinned Qwen3-4B weights; local Python 3.11+ runs the client. This baseline pins vLLM v0.11.2 and disables prefix caching in both modes. It uses n-gram proposals, not a second draft-model checkpoint.

```bash
python -m pip install -r requirements.txt
polyaxon run -f service.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=baseline
polyaxon ops service -p YOUR_PROJECT -uid BASELINE_UUID --external --url
export SERVICE_URL='PASTE_THE_RETURNED_BASELINE_URL'
export POLYAXON_TOKEN='YOUR_CONFIGURED_POLYAXON_TOKEN'
python bench.py --concurrency 1 --repeats 10 --service-run BASELINE_UUID --out baseline-c1
python bench.py --concurrency 4 --repeats 10 --service-run BASELINE_UUID --out baseline-c4
python bench.py --concurrency 8 --repeats 10 --service-run BASELINE_UUID --out baseline-c8
polyaxon ops stop -p YOUR_PROJECT -uid BASELINE_UUID
```

Approve if needed; wait for health before requests. Confirm baseline Pod removal before starting the n-gram service on the same isolated GPU:

```bash
polyaxon run -f service.yaml -u . -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P mode=ngram
polyaxon ops service -p YOUR_PROJECT -uid NGRAM_UUID --external --url
export SERVICE_URL='PASTE_THE_RETURNED_NGRAM_URL'
python bench.py --concurrency 1 --repeats 10 --service-run NGRAM_UUID --out ngram-c1
python bench.py --concurrency 4 --repeats 10 --service-run NGRAM_UUID --out ngram-c4
python bench.py --concurrency 8 --repeats 10 --service-run NGRAM_UUID --out ngram-c8
python compare.py baseline-c1 ngram-c1
polyaxon ops stop -p YOUR_PROJECT -uid NGRAM_UUID
```

Repeat the entire baseline/ngram pair in reverse order with fresh output names. Keep GPU SKU, driver, server flags, image digest, model/tokenizer revision and client/network location fixed. Retain service logs/configuration separately with each UUID.

The nine supplied prompts are an illustrative corpus with copy/edit, explanatory and short-output tasks. Replace them with a frozen representative sample before drawing deployment conclusions. Requests are closed-loop, temperature zero, thinking disabled, capped at 128 output tokens; terminal reason and full text are retained. Each run warms up every case, shuffles a repeated inventory with fixed seed 19 and retains failures. Report prompt-family breakdowns from `requests.jsonl`, not only the overall summary.

TTFT means first nonempty text observed by the client; E2E ends at stream completion. Decode-time/token is a client interval estimate using the final token count, not token arrival timestamps. An SSE chunk is not a token. p95 estimates from 90 requests are exploratory; use larger repeated representative samples for decisions. `compare.py` checks paired inventories and text equality for successful greedy completions. This is a smoke check, not a mathematical proof of distribution equivalence.
