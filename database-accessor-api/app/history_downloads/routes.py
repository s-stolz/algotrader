from app.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import storage
from .schemas import AcceptJob, ClaimJob, CommitPage, HeartbeatJob, TransitionJob

router = APIRouter(prefix="/history-download-jobs")


async def perform(session, operation, *args):
    try:
        return await operation(session, *args)
    except storage.DownloadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except storage.DownloadConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Historical download conflicts with current state"
        ) from exc


@router.post("")
async def create_job(data: AcceptJob, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.create_job, data)


@router.get("")
async def list_jobs(
    market_id: int | None = Query(None, gt=0),
    active_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await storage.list_jobs(db, market_id, active_only, limit)


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await storage.read_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Historical download not found")
    return job


@router.post("/{job_id}/claim")
async def claim_job(job_id: str, data: ClaimJob, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.claim_job, job_id, data)


@router.post("/{job_id}/heartbeat")
async def heartbeat_job(job_id: str, data: HeartbeatJob, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.heartbeat_job, job_id, data)


@router.post("/{job_id}/pages")
async def commit_page(job_id: str, data: CommitPage, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.commit_page, job_id, data)


@router.post("/{job_id}/transition")
async def transition_job(job_id: str, data: TransitionJob, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.transition_job, job_id, data)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.cancel_job, job_id)


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db)):
    return await perform(db, storage.retry_job, job_id)
