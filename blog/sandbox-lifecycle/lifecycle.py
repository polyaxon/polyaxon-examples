"""Host-side lifecycle helpers for the published sandbox examples.

Source-reviewed companion; not executed as part of the article review.
Polling deadlines are checked between HTTP calls. Transport timeouts bound each
call; they are not a hard real-time bound on DNS, OS scheduling, or remote work.
"""

import json
import time
from copy import deepcopy
from pathlib import Path

from polyaxon import settings
from polyaxon.client import PolyaxonClient, RunClient
from polyaxon.exceptions import ApiException, PolyaxonClientException
from polyaxon.schemas import LifeCycle, V1Statuses
from urllib3.exceptions import HTTPError


def make_run_client(project, owner=None, run_uuid=None):
    config = deepcopy(settings.CLIENT_CONFIG)
    config.timeout = 10
    config.retries = 0
    return RunClient(
        owner=owner,
        project=project,
        run_uuid=run_uuid,
        client=PolyaxonClient(config=config),
        manual_exceptions_handling=True,
    )


def _http_status(error):
    while error is not None:
        status = getattr(error, "status", None)
        if status is not None:
            return status
        error = error.__cause__
    return None


def wait_for_status(run_client, statuses, seconds=300, interval=2):
    if seconds <= 0 or interval <= 0:
        raise ValueError("seconds and interval must be positive")
    deadline = time.monotonic() + seconds
    last_status = None
    while time.monotonic() < deadline:
        try:
            last_status, _ = run_client.get_statuses()
        except (ApiException, PolyaxonClientException, HTTPError) as error:
            code = _http_status(error)
            # Authentication, permission, and invalid-request errors fail fast.
            if code is not None and code not in {408, 429, 500, 502, 503, 504}:
                raise
        else:
            if time.monotonic() >= deadline:
                break
            if last_status in statuses:
                return last_status
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))
    raise TimeoutError(
        f"Run {run_client.run_uuid}: polling deadline reached; "
        f"last observed status={last_status!r}"
    )


def wait_for_running(run_client, seconds=300):
    status = wait_for_status(
        run_client, {V1Statuses.RUNNING} | LifeCycle.DONE_VALUES, seconds
    )
    if status != V1Statuses.RUNNING:
        raise RuntimeError(f"Run {run_client.run_uuid} reached {status} before use")
    return status


def stop_and_record(run_client, seconds=30, directory="."):
    """Attempt cleanup, confirm terminal status, and retain an honest receipt.

    API cleanup errors become a receipt, preserving the user's command error.
    The caller should reject a successful task if confirmed=False. Local receipt
    storage must also be writable; a storage error is reported in the receipt.
    """
    receipt = {
        "run_uuid": run_client.run_uuid,
        "project": run_client.project,
        "owner": run_client.owner,
        "stop_requested": False,
        "confirmed": False,
        "status": None,
    }
    try:
        status, _ = run_client.get_statuses()
        if status not in LifeCycle.DONE_VALUES:
            run_client.stop()
            receipt["stop_requested"] = True
            status = wait_for_status(run_client, LifeCycle.DONE_VALUES, seconds)
        receipt.update(confirmed=True, status=status)
    except Exception as error:
        # Do not put response bodies or credentials into a shared receipt.
        receipt["error_type"] = type(error).__name__
        receipt["next_action"] = "Inspect this run and confirm termination manually"
    output = Path(directory) / f"cleanup-{run_client.run_uuid}.json"
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    except OSError as error:
        receipt["receipt_storage_error"] = type(error).__name__
    print(json.dumps(receipt))
    return receipt
