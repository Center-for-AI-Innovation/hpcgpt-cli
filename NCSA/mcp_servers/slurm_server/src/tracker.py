"""Read-only, structured Slurm job tracking."""

from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable


CommandRunner = Callable[[list[str]], str]

_USERNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_JOB_ID_RE = re.compile(r"^\d+(?:_\d+)?(?:\+\d+)?$")
_LOOKBACK_RE = re.compile(r"^[1-9]\d{0,2}[mhdw]$")
_LOOKBACK_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
_MAX_LOOKBACK_SECONDS = 90 * 86400
_COMMAND_TIMEOUT_SECONDS = 20

ACTIVE_STATES = {
    "CONFIGURING",
    "COMPLETING",
    "PENDING",
    "RUNNING",
    "RESIZING",
    "REQUEUED",
    "REQUEUE_FED",
    "REQUEUE_HOLD",
    "SIGNALING",
    "STAGE_OUT",
    "SUSPENDED",
}


class SlurmCommandError(RuntimeError):
    """Raised when Slurm cannot return valid structured data."""


def process_username() -> str:
    """Return the effective Unix account, without trusting environment variables."""
    return pwd.getpwuid(os.geteuid()).pw_name


def run_json_command(command: list[str]) -> str:
    """Run a fixed argv command and return stdout."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise SlurmCommandError(f"Slurm command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SlurmCommandError(
            f"{command[0]} did not finish within {_COMMAND_TIMEOUT_SECONDS} seconds"
        ) from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "No error output").strip()
        raise SlurmCommandError(
            f"{' '.join(command)} failed with exit code {result.returncode}: {details}"
        )
    return result.stdout


def _number(value: Any) -> int | float | None:
    if isinstance(value, dict) and "number" in value:
        if value.get("set") is False or value.get("infinite") is True:
            return None
        value = value["number"]
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _timestamp(value: Any) -> str | None:
    seconds = _number(value)
    if not seconds:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _duration(seconds: Any) -> str | None:
    value = _number(seconds)
    if value is None:
        return None
    value = int(value)
    days, remainder = divmod(value, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    prefix = f"{days}-" if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"


def _state(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("current", value.get("state", "UNKNOWN"))
    if isinstance(value, list):
        return str(value[0]) if value else "UNKNOWN"
    return str(value or "UNKNOWN")


def _state_reason(value: Any) -> str | None:
    if isinstance(value, dict):
        reason = value.get("reason")
        if reason and reason != "None":
            return str(reason)
    return None


def _user_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name") or value.get("user")
    return str(value) if value else None


def _tres(items: Any) -> dict[str, int | float]:
    if not isinstance(items, list):
        return {}
    resources: dict[str, int | float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        resource_type = item.get("type")
        if not resource_type:
            continue
        name = item.get("name")
        key = f"{resource_type}/{name}" if name else str(resource_type)
        count = _number(item.get("count"))
        if count is not None:
            resources[key] = count
    return resources


def _exit_code(value: Any) -> str | None:
    if not isinstance(value, dict):
        return str(value) if value else None
    return_code = _number(value.get("return_code"))
    signal = value.get("signal", {})
    signal_id = _number(signal.get("id")) if isinstance(signal, dict) else None
    if return_code is None and signal_id is None:
        return None
    return f"{int(return_code or 0)}:{int(signal_id or 0)}"


def _job_id(job: dict[str, Any]) -> str:
    value = job.get("job_id") or job.get("job_id_str") or job.get("id")
    result = str(value) if value is not None else ""
    array = job.get("array") if isinstance(job.get("array"), dict) else {}
    task_id = _number(array.get("task_id") or job.get("array_task_id"))
    if task_id is not None and "_" not in result:
        result = f"{result}_{int(task_id)}"
    return result


def normalize_job(job: dict[str, Any], source: str) -> dict[str, Any]:
    """Normalize the overlapping squeue/sacct job fields used by the UI."""
    time = job.get("time") if isinstance(job.get("time"), dict) else {}
    required = job.get("required") if isinstance(job.get("required"), dict) else {}
    tres = job.get("tres") if isinstance(job.get("tres"), dict) else {}
    nodes = job.get("nodes")
    if isinstance(nodes, dict):
        nodes = nodes.get("range") or ",".join(nodes.get("list", []))

    state_value = job.get("state") or job.get("job_state")
    return {
        "job_id": _job_id(job),
        "name": job.get("name") or job.get("job_name") or "",
        "user": _user_name(job.get("user")),
        "account": job.get("account"),
        "partition": job.get("partition"),
        "qos": job.get("qos"),
        "state": _state(state_value),
        "state_reason": _state_reason(state_value) or job.get("state_reason"),
        "nodes": nodes,
        "node_count": _number(job.get("allocation_nodes"))
        or _number(job.get("node_count")),
        "cpus": _number(required.get("CPUs")) or _number(job.get("cpus")),
        "resources": _tres(tres.get("allocated") or tres.get("requested")),
        "submitted_at": _timestamp(time.get("submission") or job.get("submit_time")),
        "started_at": _timestamp(time.get("start") or job.get("start_time")),
        "ended_at": _timestamp(time.get("end") or job.get("end_time")),
        "elapsed": _duration(time.get("elapsed")),
        "time_limit_minutes": _number(time.get("limit") or job.get("time_limit")),
        "exit_code": _exit_code(job.get("exit_code")),
        "stdout": job.get("stdout_expanded") or job.get("stdout"),
        "stderr": job.get("stderr_expanded") or job.get("stderr"),
        "working_directory": job.get("working_directory"),
        "source": source,
    }


def _parse_payload(text: str, command_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SlurmCommandError(f"{command_name} returned invalid JSON") from exc
    errors = payload.get("errors", [])
    if errors:
        descriptions = [str(item.get("description", item)) for item in errors]
        raise SlurmCommandError(f"{command_name} reported: {'; '.join(descriptions)}")
    return payload


def _slurm_start_time(lookback: str) -> str:
    units = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
    return f"now-{lookback[:-1]}{units[lookback[-1]]}"


class SlurmTracker:
    """Query Slurm and expose a compact, user-scoped job view."""

    def __init__(
        self,
        identity_mode: str = "explicit",
        runner: CommandRunner = run_json_command,
    ) -> None:
        if identity_mode not in {"explicit", "process"}:
            raise ValueError("identity_mode must be 'explicit' or 'process'")
        self.identity_mode = identity_mode
        self.runner = runner

    def resolve_username(self, username: str | None) -> str:
        resolved = process_username() if self.identity_mode == "process" else username
        if not resolved:
            raise ValueError("username is required for a remote Slurm tracker")
        if not _USERNAME_RE.fullmatch(resolved):
            raise ValueError("invalid username")
        return resolved

    @staticmethod
    def validate_job_id(job_id: str) -> str:
        if not _JOB_ID_RE.fullmatch(job_id):
            raise ValueError("job_id must be a numeric Slurm job or array task ID")
        return job_id

    @staticmethod
    def validate_lookback(since: str) -> str:
        if not _LOOKBACK_RE.fullmatch(since):
            raise ValueError("since must be 1-999 followed by m, h, d, or w")
        seconds = int(since[:-1]) * _LOOKBACK_SECONDS[since[-1]]
        if seconds > _MAX_LOOKBACK_SECONDS:
            raise ValueError("since cannot exceed 90 days")
        return since

    def _jobs(self, command: list[str], source: str) -> list[dict[str, Any]]:
        payload = _parse_payload(self.runner(command), command[0])
        return [normalize_job(job, source) for job in payload.get("jobs", [])]

    def list_jobs(
        self,
        username: str | None = None,
        states: list[str] | None = None,
        since: str = "24h",
        limit: int = 50,
        include_completed: bool = True,
    ) -> dict[str, Any]:
        user = self.resolve_username(username)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        requested_states = {state.upper() for state in states or []}
        lookback = self.validate_lookback(since)

        jobs = self._jobs(["squeue", "--json", "-u", user], "squeue")
        sources = ["squeue"]
        if include_completed:
            jobs.extend(
                self._jobs(
                    ["sacct", "-X", "--json", "-u", user, "-S", _slurm_start_time(lookback)],
                    "sacct",
                )
            )
            sources.append("sacct")

        merged: dict[str, dict[str, Any]] = {}
        for job in jobs:
            job_id = job["job_id"]
            if not job_id or job.get("user") not in {None, user}:
                continue
            existing = merged.get(job_id)
            if existing and existing["source"] == "squeue":
                continue
            merged[job_id] = job

        filtered = [
            job for job in merged.values()
            if not requested_states or job["state"] in requested_states
        ]
        filtered.sort(
            key=lambda job: (
                job["state"] in ACTIVE_STATES,
                job.get("submitted_at") or "",
                job["job_id"],
            ),
            reverse=True,
        )
        filtered = filtered[:limit]
        return {
            "username": user,
            "jobs": filtered,
            "count": len(filtered),
            "active_count": sum(job["state"] in ACTIVE_STATES for job in filtered),
            "history_lookback": lookback if include_completed else None,
            "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sources": sources,
        }

    def get_job(self, job_id: str, username: str | None = None) -> dict[str, Any]:
        user = self.resolve_username(username)
        job_id = self.validate_job_id(job_id)
        # Some Slurm versions fail instead of returning an empty list when -j
        # names a completed job, so query the user's active queue and filter it.
        active = self._jobs(["squeue", "--json", "-u", user], "squeue")
        history = self._jobs(["sacct", "-X", "--json", "-u", user, "-j", job_id], "sacct")
        matches = [
            job for job in active + history
            if job["job_id"] == job_id and job.get("user") in {None, user}
        ]
        if not matches:
            raise ValueError(f"job {job_id} was not found for user {user}")
        job = next((item for item in matches if item["source"] == "squeue"), matches[0])
        return {"username": user, "job": job}

    def get_job_usage(self, job_id: str, username: str | None = None) -> dict[str, Any]:
        user = self.resolve_username(username)
        job_id = self.validate_job_id(job_id)
        payload = _parse_payload(
            self.runner(["sacct", "--json", "-u", user, "-j", job_id]),
            "sacct",
        )
        matching = [
            job for job in payload.get("jobs", [])
            if _job_id(job) == job_id and _user_name(job.get("user")) in {None, user}
        ]
        if not matching:
            raise ValueError(f"job {job_id} was not found for user {user}")
        raw_job = matching[0]
        steps = []
        for step in raw_job.get("steps", []):
            tres = step.get("tres") if isinstance(step.get("tres"), dict) else {}
            steps.append({
                "step_id": step.get("step", {}).get("id") if isinstance(step.get("step"), dict) else None,
                "name": step.get("step", {}).get("name") if isinstance(step.get("step"), dict) else None,
                "state": _state(step.get("state")),
                "elapsed": _duration(step.get("time", {}).get("elapsed")) if isinstance(step.get("time"), dict) else None,
                "tasks": _number(step.get("tasks", {}).get("count")) if isinstance(step.get("tasks"), dict) else None,
                "allocated": _tres(tres.get("allocated")),
                "maximum": _tres(tres.get("requested", {}).get("max")) if isinstance(tres.get("requested"), dict) else {},
                "average": _tres(tres.get("requested", {}).get("average")) if isinstance(tres.get("requested"), dict) else {},
                "consumed": _tres(tres.get("consumed", {}).get("total")) if isinstance(tres.get("consumed"), dict) else {},
            })
        return {
            "username": user,
            "job": normalize_job(raw_job, "sacct"),
            "steps": steps,
            "note": "Usage fields depend on the accounting data collected by this cluster.",
        }
