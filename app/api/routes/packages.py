"""Package generation API endpoints."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import get_package_service
from app.core.exceptions import ReTourError
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import PackageGenerationResponse
from app.services.job_store import JobStatus, get_job_store
from app.services.package_service import PackageService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/packages", tags=["packages"])


class AsyncGenerateResponse(BaseModel):
    success: bool = True
    jobId: str
    status: str = JobStatus.QUEUED.value
    message: str = "Generation started. Poll /api/v1/packages/jobs/{jobId}."


class JobStatusResponse(BaseModel):
    success: bool = True
    jobId: str
    status: str
    error: str | None = None
    result: PackageGenerationResponse | None = None
    elapsedSec: float = Field(0, description="Seconds since job creation")
    stage: str = ""
    stageLabel: str = ""


@router.post(
    "/generate",
    response_model=PackageGenerationResponse,
    summary="Generate a personalized tourism package (blocking)",
)
async def generate_package(
    request: PackageRequest,
    service: PackageService = Depends(get_package_service),
) -> PackageGenerationResponse:
    """Blocking generate — used by scripts. Prefer /generate/async from the UI."""
    return await service.generate(request)


@router.post(
    "/generate/async",
    response_model=AsyncGenerateResponse,
    summary="Start package generation in the background",
)
async def generate_package_async(
    request: PackageRequest,
    service: PackageService = Depends(get_package_service),
) -> AsyncGenerateResponse:
    """
    Returns immediately with a jobId. The browser should poll
    GET /packages/jobs/{jobId} until status is succeeded|failed.
    """
    store = get_job_store()
    job = await store.create()
    asyncio.create_task(_run_job(job.job_id, request, service))
    return AsyncGenerateResponse(jobId=job.job_id, status=job.status.value)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll async package generation job status",
)
async def get_package_job(job_id: str) -> JobStatusResponse:
    store = get_job_store()
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "This generation job is no longer on the server "
                "(Brain restarted). Click Generate again."
            ),
        )

    result = None
    if job.status == JobStatus.SUCCEEDED and job.result is not None:
        result = PackageGenerationResponse.model_validate(job.result)

    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status.value,
        error=job.error,
        result=result,
        elapsedSec=round(time.time() - job.created_at, 1),
        stage=job.stage,
        stageLabel=job.stage_label,
    )


async def _run_job(
    job_id: str,
    request: PackageRequest,
    service: PackageService,
) -> None:
    store = get_job_store()
    await store.set_running(job_id, "running", "Planning your trip")

    async def on_stage(stage: str, label: str) -> None:
        await store.set_stage(job_id, stage, label)

    try:
        response = await service.generate_with_progress(request, on_stage)
        await store.set_succeeded(job_id, response.model_dump(mode="json"))
        logger.info("Async job %s succeeded", job_id)
    except ReTourError as exc:
        logger.warning("Async job %s failed: %s", job_id, exc.message)
        await store.set_failed(job_id, exc.message)
    except Exception as exc:  # noqa: BLE001 — surface unexpected errors to the UI
        logger.exception("Async job %s crashed", job_id)
        await store.set_failed(job_id, str(exc) or "Package generation failed")
