"""Bounded local adapter; source-reviewed, not execution-verified.

The operator supplies actor, policy, and a private persistent SQLite path. These
are not tool arguments. This example is not an HTTP authentication service.
"""

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lifecycle import make_run_client


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    dataset: str = Field(min_length=1, max_length=64)
    candidate: str = Field(min_length=1, max_length=64)


class Adapter:
    def __init__(self):
        policy_path = Path(os.environ["POLYAXON_MCP_POLICY"]).resolve()
        self.actor = os.environ["POLYAXON_MCP_ACTOR"]
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.profile = policy["actors"][self.actor]
        self.operation = (policy_path.parent / self.profile["operation"]).resolve()
        self.db_path = Path(os.environ["POLYAXON_MCP_STATE"]).resolve()
        # The parent directory must already be private to the operator.
        fd = os.open(self.db_path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                actor TEXT NOT NULL, request_key TEXT NOT NULL,
                request_id TEXT UNIQUE NOT NULL, fingerprint TEXT NOT NULL,
                state TEXT NOT NULL, run_uuid TEXT,
                PRIMARY KEY(actor, request_key)
            )""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def client(self, run_uuid=None):
        return make_run_client(
            owner=self.profile["owner"], project=self.profile["project"],
            run_uuid=run_uuid,
        )

    @staticmethod
    def receipt(row):
        return {
            "request_id": row["request_id"],
            "submission_state": row["state"],
            "run_uuid": row["run_uuid"],
        }

    def submit(self, arguments):
        request = SubmitRequest.model_validate(arguments)
        dataset = self.profile["datasets"].get(request.dataset)
        if dataset is None or request.candidate not in dataset["predictions"]:
            return {"submission_state": "rejected", "reason": "Not an approved dataset/candidate"}
        fingerprint = hashlib.sha256(
            json.dumps(request.model_dump(), sort_keys=True).encode()
        ).hexdigest()
        # Commit intent BEFORE dispatch. All concurrent calls use this constraint.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM requests WHERE actor=? AND request_key=?",
                (self.actor, request.request_key),
            ).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    return {"submission_state": "rejected", "reason": "Request key already binds different arguments"}
                return self.receipt(row)
            count = db.execute(
                "SELECT COUNT(*) FROM requests WHERE actor=?", (self.actor,)
            ).fetchone()[0]
            if count >= self.profile["max_submissions"]:
                return {"submission_state": "rejected", "reason": "Operator submission budget exhausted"}
            request_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?, 'submitting', NULL)",
                (self.actor, request.request_key, request_id, fingerprint),
            )
        client = None
        try:
            client = self.client()
            run = client.create_from_polyaxonfile(
                polyaxonfile=str(self.operation),
                params={
                    "manifest_file": dataset["manifest"],
                    "predictions_file": dataset["predictions"][request.candidate],
                    "candidate_revision": request.candidate,
                    "minimum_score": 0.90,
                },
                tags=[f"mcp-request-{request_id}"],
                approved=True,
            )
        except Exception:
            # The API may have accepted the request before the response was lost.
            with self.connect() as db:
                db.execute(
                    "UPDATE requests SET state='uncertain' WHERE request_id=?",
                    (request_id,),
                )
            return {"request_id": request_id, "submission_state": "uncertain", "run_uuid": None}
        finally:
            if client is not None:
                client.client.close()
        with self.connect() as db:
            db.execute(
                "UPDATE requests SET state='submitted', run_uuid=? WHERE request_id=?",
                (run.uuid, request_id),
            )
        return {"request_id": request_id, "submission_state": "submitted", "run_uuid": run.uuid}

    def inspect(self, request_id):
        if not isinstance(request_id, str) or len(request_id) != 32:
            return {"submission_state": "not_found"}
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE actor=? AND request_id=?",
                (self.actor, request_id),
            ).fetchone()
        if row is None:
            return {"submission_state": "not_found"}
        receipt = self.receipt(row)
        if row["run_uuid"]:
            client = None
            try:
                client = self.client(row["run_uuid"])
                status, _ = client.get_statuses()
                receipt["run_status"] = status
            except Exception:
                receipt["inspection"] = "unavailable"
            finally:
                if client is not None:
                    client.client.close()
        # Never infer candidate quality solely from a successful run status.
        receipt["quality_decision"] = "inspect_evaluation_report"
        return receipt
