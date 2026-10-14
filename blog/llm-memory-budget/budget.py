"""Analytical tensor capacity, not measured GPU memory or a fit guarantee."""
import argparse
import json


def estimate(layers, kv_heads, head_dim, tokens, sequences, kv_bytes):
    return 2 * layers * kv_heads * head_dim * tokens * sequences * kv_bytes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokens", type=int, default=4096)
    parser.add_argument("--sequences", type=int, default=8)
    parser.add_argument("--kv-bytes", type=int, choices=[1, 2, 4], default=2)
    args = parser.parse_args()
    if args.tokens < 1 or args.sequences < 1:
        parser.error("tokens and sequences must be positive")
    kv = estimate(36, 8, 128, args.tokens, args.sequences, args.kv_bytes)
    weights = 8044936192
    print(json.dumps({
        "model": "Qwen/Qwen3-4B",
        "revision": "1cfa9a7208912126459214e8b04321603b3df60c",
        "serialized_weight_bytes": weights, "kv_tensor_bytes": kv,
        "weights_plus_kv_gib": (weights + kv) / 2**30,
        "assumptions": {
            "layers": 36, "kv_heads": 8, "head_dim": 128,
            "bytes_per_kv_element": args.kv_bytes, "tokens_per_sequence": args.tokens,
            "sequences": args.sequences, "shared_prefixes": False,
            "excluded": ["block padding", "activations", "CUDA graphs", "workspace",
                         "allocator reserve", "quantization scales", "other processes"],
        },
    }, indent=2))
