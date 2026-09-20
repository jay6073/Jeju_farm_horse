"""예산 비교 작업 저장/불러오기 API (Supabase 저장)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from repository import budget_work_repository as repo

router = APIRouter(prefix="/api/budget", tags=["budget"])

MAX_ITEMS = 2000


class WorkIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    payload: dict


def _validate_payload(payload: dict) -> None:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail="작업 내용(items)이 비어 있습니다.")
    if len(items) > MAX_ITEMS:
        raise HTTPException(status_code=422, detail="항목 수가 너무 많습니다.")


@router.get("/works")
def list_works():
    return repo.list_works()


@router.get("/works/{work_id}")
def get_work(work_id: UUID):
    work = repo.get_work(work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return work


@router.post("/works", status_code=201)
def create_work(body: WorkIn):
    _validate_payload(body.payload)
    return repo.create_work(body.title.strip(), body.payload)


@router.put("/works/{work_id}")
def update_work(work_id: UUID, body: WorkIn):
    _validate_payload(body.payload)
    work = repo.update_work(work_id, body.title.strip(), body.payload)
    if work is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return work


@router.delete("/works/{work_id}", status_code=204)
def delete_work(work_id: UUID):
    if not repo.delete_work(work_id):
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return Response(status_code=204)
