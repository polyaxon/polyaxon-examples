# Polyaxon blog examples

Companion code and fixtures for the [Polyaxon blog](https://polyaxon.com/blog/).

Clone the repository once, then enter the directory for the article you are following:

```bash
git clone https://github.com/polyaxon/polyaxon-examples.git
cd polyaxon-examples/blog
```

If you already have a checkout, use its `blog/` directory. Keep the source revision with any results you collect.

## Examples

| Directory | Contents and article | Prerequisites |
| --- | --- | --- |
| [evaluation-data-leakage](evaluation-data-leakage/) | Synthetic support-case fixture, grouped split preparation, overlap reports, manifests, and an optional tracked job for the draft article **Prevent data leakage in ML and LLM evaluation datasets**. Publication pending. | Python 3.11+ and the supplied requirements locally; a configured Polyaxon CLI/deployment with artifact storage and image/package-index access for the optional job. Upload the folder with `-u`; dependencies install at startup. Source-reviewed; not executed. |
| [ai-security-evals](ai-security-evals/) | Deterministic Promptfoo suite, provider fixture, runner, and container for [Promptfoo evaluations on Kubernetes](https://polyaxon.com/blog/run-promptfoo-evaluations-on-kubernetes/). | Node.js 22.22.0+ and Python 3.9+ locally, or Docker for the packaged workflow. Cluster execution also needs a configured Polyaxon deployment and a reachable image registry. Use this directory as the Docker build context. |
| [agent-evaluators](agent-evaluators/) | Exact-match evaluator, trusted manifest, and four prediction fixtures for [shared agent evaluators](https://polyaxon.com/blog/build-a-shared-library-of-agent-evaluators/). | Python 3.11+ for local fixture evaluation. Tracked execution also needs a deployment-compatible Polyaxon client, your evaluator image, registered component, and configured data connection. |
| [sandbox-lifecycle](sandbox-lifecycle/) | Shared run-client and cleanup helper for [sandbox lifecycle](https://polyaxon.com/blog/ai-sandbox-lifecycle/), [code execution workspaces](https://polyaxon.com/blog/set-up-a-polyaxon-code-execution-workspace/), and [coding-agent sandboxes](https://polyaxon.com/blog/manage-ai-coding-agent-sandboxes/). | Python 3.11+, a configured Polyaxon client, an existing project, service-launch permissions, and sandbox support on the compute agent. Save the chosen article's component and controller beside `lifecycle.py`. |
| [sandbox-benchmark](sandbox-benchmark/) | Fixed workload, host harness, sandbox component, and tracked controller for [sandbox benchmarks](https://polyaxon.com/blog/benchmark-coding-agent-sandboxes-with-polyaxon/). | Sandbox lifecycle prerequisites, the helper-copy step below, and a reviewed sandbox image. The tracked controller additionally requires your own image containing the harness and its dependencies. |
| [polyaxon-mcp](polyaxon-mcp/) | Local stdio server, adapter, policy, operation, and ordered request fixtures for [connecting MCP tools to Polyaxon](https://polyaxon.com/blog/build-mcp-tools-for-polyaxon-workflows/). | Python 3.11+, a deployment-compatible Polyaxon client, the official MCP Python SDK v2 interface, the helper-copy step below, and the article's registered evaluator and operator-controlled configuration. |
| [durable-agent-recovery](durable-agent-recovery/) | Illustrative application records for [durable agent execution](https://polyaxon.com/blog/durable-execution-for-ai-agents/). | A JSON viewer; this is an application contract fixture, not an executable recovery service or a Polyaxon schema. |
| [otel-collector](otel-collector/) | Collector configuration and synthetic trace sender for [OpenTelemetry on ML platforms](https://polyaxon.com/blog/opentelemetry-collector-for-ml-platforms/). | Docker and Python 3. Run the article's commands from this directory so the configuration bind mount resolves correctly. |
| [ml-service-load-test](ml-service-load-test/) | k6 script, input fixtures, Dockerfile, and Polyaxonfile for [load-testing ML services](https://polyaxon.com/blog/load-test-ml-services-on-kubernetes/). | k6 and a staging endpoint matching the article's request/response contract. Polyaxon execution also needs your built image and deployment configuration. Use this directory as the Docker build context. |

## Prepare the shared lifecycle helper

The benchmark and MCP adapter import `lifecycle.py`. Keep its maintained source in `sandbox-lifecycle/` and copy it into the selected example's working directory during setup.

For the benchmark, starting in `polyaxon-examples/blog`:

```bash
cd sandbox-benchmark
cp ../sandbox-lifecycle/lifecycle.py .
```

For the MCP adapter, starting in `polyaxon-examples/blog`:

```bash
cd polyaxon-mcp
cp ../sandbox-lifecycle/lifecycle.py .
cp policy.example.json policy.json
```

Repeat the helper-copy step after updating its source. Include the prepared helper when packaging the benchmark controller image. Keep MCP policy and state paths absolute, and keep its configured identity, policy, credentials, and persistent ledger outside the agent's writable workspace. Follow the article's setup before starting the server.

## Execution and results

Review and execution status is recorded in each article. The Promptfoo walkthrough records prior local fixture results; the other companion groups were source-reviewed and include expected or illustrative outcomes. Moving these files adds no runtime verification. The articles describe configuration, execution, evidence collection, and cleanup. Sandbox controllers and MCP submission tools create real remote runs when executed; the load generator sends traffic to the configured endpoint.
