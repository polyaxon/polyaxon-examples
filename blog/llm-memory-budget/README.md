# LLM memory budget

Companion for `size-gpu-memory-for-llm-serving`. Source-reviewed October 14, 2026; no GPU workload executed. Calculator output is analytical tensor storage, not measured process memory or proof that a deployment fits.

The calculator uses the pinned Qwen3-4B configuration (36 layers, 8 KV heads, head dimension 128) and checkpoint index (8,044,936,192 serialized weight bytes). Its dense, full-attention estimate assumes distinct token storage, no shared prefixes and no tensor parallelism.

```bash
python budget.py --tokens 4096 --sequences 8 --kv-bytes 2
```

`--tokens` includes prompt and generated tokens per live sequence. The estimate excludes graph/workspace buffers, transient activations, page padding, allocator reserve and other engine state. Weight quantization does not change KV precision automatically.

For a configured Polyaxon GPU project, the service fixes Qwen3-4B and vLLM v0.11.2 revisions and exposes length/sequence settings:

```bash
polyaxon run -f service.yaml -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE -P max_model_len=4096 -P max_num_seqs=8
polyaxon ops logs -p YOUR_PROJECT -uid SERVICE_UUID
polyaxon ops service -p YOUR_PROJECT -uid SERVICE_UUID --external --url
```

Approve if required. Use one dedicated GPU for the baseline, inspect vLLM's actual startup memory/KV capacity and send representative requests before raising length or client concurrency. `max_num_seqs` controls sequences scheduled per iteration; it is not a hard limit on all clients admitted to the HTTP API. Node drivers must support the image and nodes need model download access. Stop when done:

```bash
polyaxon ops stop -p YOUR_PROJECT -uid SERVICE_UUID
```
