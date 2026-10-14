import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["baseline", "ngram"], required=True)
args = parser.parse_args()
command = [
    "vllm", "serve", "Qwen/Qwen3-4B",
    "--revision", "1cfa9a7208912126459214e8b04321603b3df60c",
    "--tokenizer-revision", "1cfa9a7208912126459214e8b04321603b3df60c",
    "--served-model-name", "qwen-study", "--max-model-len", "2048",
    "--max-num-seqs", "8", "--gpu-memory-utilization", "0.85",
    "--no-enable-prefix-caching",
    "--host", "0.0.0.0", "--port", "8000",
]
if args.mode == "ngram":
    command += ["--speculative-config", '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_min":2,"prompt_lookup_max":4}']
os.execvp(command[0], command)
