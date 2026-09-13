"""Fixed synthetic workload; it does not call a model or external service."""
import json
from pathlib import Path

root = Path("/workspace")
request = json.loads((root / "input.json").read_text(encoding="utf-8"))
state = root / "sequence.txt"
sequence = int(state.read_text()) + 1 if state.exists() else 1
state.write_text(str(sequence), encoding="utf-8")
(root / "report.json").write_text(
    json.dumps({
        "trial_id": request["trial_id"],
        "total": sum(request["values"]),
        "sequence": sequence,
    }),
    encoding="utf-8",
)
