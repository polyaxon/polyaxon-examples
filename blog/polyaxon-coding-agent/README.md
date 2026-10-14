# A bounded coding agent using Polyaxon sandboxes

Companion for `build-a-coding-agent-with-polyaxon-sandboxes`. Source-reviewed October 14, 2026; no agent/model requests, checks or sandbox runs executed. No success rate is claimed.

Requirements: configured deployment-compatible Polyaxon Python client/CLI (native SandboxClient support, 2.16.2+), sandbox support on the compute agent, a project with service creation/approval/stop permissions, separate CPU and NVIDIA GPU queues, compatible GPU drivers and Hugging Face access for the model service. Run the controller in your configured local environment. Keep its credentials outside the model workspace.

```bash
python -m pip install -r requirements.txt
polyaxon run -f model.yaml -p YOUR_PROJECT --queue YOUR_AGENT/YOUR_GPU_QUEUE
polyaxon ops service -p YOUR_PROJECT -uid MODEL_UUID --external --url
export SERVICE_URL='PASTE_THE_RETURNED_URL'
export POLYAXON_TOKEN='YOUR_CONFIGURED_POLYAXON_TOKEN'
python agent.py --owner YOUR_ORG --project YOUR_PROJECT --queue YOUR_AGENT/YOUR_CPU_QUEUE --allow-checks --out agent-output
```

Approve the model service if required and wait until healthy. `--allow-checks` explicitly authorizes the supplied fixed unittest command in the disposable CPU workspace. The controller automatically approves the workspace run after creation. Do not invoke it unless you intend those remote actions.

The fixture starts with a float-based amount parser. Four trusted cases require Decimal output, separators, whitespace handling and invalid-input rejection. The model selects one JSON action per turn (read, write, check, finish). The controller permits reads of the two fixture files, writes only `amounts.py`, and executes only the fixed check command. It restores trusted check source before execution and compares file bytes afterward; finishing requires the currently checked patch and unchanged fixture. It stores a transcript, patch, outcome and workspace UUID. A 12-turn budget bounds the interaction.

This is a benign teaching fixture, not an adversarial evaluation or a secure verifier. Python under test runs inside the workspace and can act with that container's authority. File hashes do not protect an already compromised interpreter or prove implementation correctness. A production verifier needs an independent trusted environment, hidden cases and appropriate filesystem/network/runtime controls. Sandbox service termination and run status are separate from task acceptance.

The controller requests workspace stop in `finally`; inspect its recorded UUID/status if the controller loses connectivity. A 30-minute workspace timeout and two-hour model-service timeout provide additional bounds. Stop the model service after the experiment:

```bash
polyaxon ops stop -p YOUR_PROJECT -uid MODEL_UUID
```

Preserve the companion commit, model/image revisions, controller configuration, action transcript, patch and check outputs. Current sandbox execution APIs are used; proposed autoresearch campaign features are not assumed.
