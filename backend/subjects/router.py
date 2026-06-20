from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from authentication.auth import get_optional_user, require_admin
from subjects.crud import subject_list, subject_create, subject_delete

router = APIRouter(prefix="/api/subjects", tags=["subjects"])

class SubjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

@router.get("")
async def list_subjects(user: Optional[dict] = Depends(get_optional_user)):
    """
    List all subjects.  Anyone may call this to filter chat queries.
    """
    return subject_list()

@router.post("", status_code=201)
async def create_subject(
    body: SubjectCreate,
    user: dict = Depends(require_admin),
):
    """
    Create a new subject.  **Admin only.**

    - Raises **409** if a subject with the same name already exists.
    """
    try:
        return subject_create(body.name, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.delete("/{subject_id}", status_code=200)
async def delete_subject(
    subject_id: int,
    user: dict = Depends(require_admin),
):
    """
    Delete a subject by ID (cascade-deletes linked sources).  **Admin only.**

    - Raises **404** if the subject does not exist.
    """
    deleted = subject_delete(subject_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")
    return {"status": "deleted", "id": subject_id}
