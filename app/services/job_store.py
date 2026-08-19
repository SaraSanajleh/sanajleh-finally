"""Package generation job store — memory plus disk so reloads keep job IDs."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.config.settings import PROJECT_ROOT


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class PackageJob:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str | None = None
    result: dict[str, Any] | None = None
    stage: str = "queued"
    stage_label: str = "Waiting to start"

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageJob:
        return cls(
            job_id=str(data["job_id"]),
            status=JobStatus(data.get("status") or JobStatus.QUEUED),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            error=data.get("error"),
            result=data.get("result") if isinstance(data.get("result"), dict) else None,
            stage=str(data.get("stage") or "queued"),
            stage_label=str(data.get("stage_label") or "Waiting to start"),
        )


class PackageJobStore:
    """Job registry that survives uvicorn reloads."""

    def __init__(self, root: Path | None = None) -> None:
        self._jobs: dict[str, PackageJob] = {}
        self._lock = asyncio.Lock()
        self._dir = root or (PROJECT_ROOT / "case_capture" / "jobs")
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.json"

    def _write(self, job: PackageJob) -> None:
        path = self._path(job.job_id)
        path.write_text(json.dumps(job.to_dict(), ensure_ascii=False), encoding="utf-8")

    def _read(self, job_id: str) -> PackageJob | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return PackageJob.from_dict(data)

    async def create(self) -> PackageJob:
        job = PackageJob(job_id=str(uuid.uuid4()))
        async with self._lock:
            self._jobs[job.job_id] = job
            self._write(job)
        return job

    async def get(self, job_id: str) -> PackageJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job
            job = self._read(job_id)
            if job is None:
                return None
            # File exists but this process never ran the worker — Brain restarted.
            if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                job.status = JobStatus.FAILED
                job.error = (
                    "The Brain restarted during generation. Click Generate My Package again."
                )
                job.stage = "failed"
                job.stage_label = "Interrupted"
                job.touch()
                self._write(job)
            self._jobs[job_id] = job
            return job

    async def set_running(self, job_id: str, stage: str = "running", stage_label: str = "Planning") -> None:
        async with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job:
                return
            job.status = JobStatus.RUNNING
            job.stage = stage
            job.stage_label = stage_label
            job.touch()
            self._jobs[job_id] = job
            self._write(job)

    async def set_stage(self, job_id: str, stage: str, stage_label: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job:
                return
            job.stage = stage
            job.stage_label = stage_label
            job.touch()
            self._jobs[job_id] = job
            self._write(job)

    async def set_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job:
                return
            job.status = JobStatus.SUCCEEDED
            job.result = result
            job.error = None
            job.touch()
            self._jobs[job_id] = job
            self._write(job)

    async def set_failed(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job:
                return
            job.status = JobStatus.FAILED
            job.error = error
            job.touch()
            self._jobs[job_id] = job
            self._write(job)


_store = PackageJobStore()


def get_job_store() -> PackageJobStore:
    return _store
