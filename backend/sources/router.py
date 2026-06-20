import os
import aiofiles
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from authentication.auth import require_auth, require_admin, get_current_tenant
from subjects.crud import subject_get
from sources.crud import source_create, source_get, source_delete, source_update_status, source_list_by_subject

from chat.rag_backend import ingest_file, remove_source_from_vector_db

router = APIRouter(prefix="/api", tags=["sources"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_data")


@router.get("/admin/subjects/{subject_id}/sources")
async def admin_list_sources(
    subject_id: int,
    _user: dict = Depends(require_admin),
):
    """List all sources for a subject (admin only)."""
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return source_list_by_subject(subject_id)


@router.delete("/admin/subjects/{subject_id}/sources/{source_id}", status_code=200)
async def admin_delete_source(
    subject_id: int,
    source_id: int,
    tenant_id: str = Depends(get_current_tenant),
    _user: dict = Depends(require_admin),
):
    """
    Admin endpoint: remove a source and purge its chunks from the vector store.
    """
    source = source_get(source_id)
    if not source or source["subject_id"] != subject_id:
        raise HTTPException(status_code=404, detail="Source not found.")

    chunks_removed = remove_source_from_vector_db(tenant_id, source_id)

    file_path = source.get("file_ref", "")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as exc:
            print(f"[WARN] Could not delete file {file_path}: {exc}")

    source_delete(source_id)

    return {
        "status": "deleted",
        "source_id": source_id,
        "chunks_removed": chunks_removed,
    }


def _ingest_global_source(
    tenant_id: str,
    file_path: str,
    filename: str,
    source_id: int,
    subject_id: int,
):
    """
    Background task: ingest the file with global provenance metadata,
    then flip the source status to 'ready' (or 'failed').
    """
    try:
        ingest_file(
            tenant_id,
            file_path,
            filename,
            source_id=source_id,
            subject_id=subject_id,
            owner_id=None,
            visibility="global",
        )
        source_update_status(source_id, "ready")
        print(f"[ADMIN] Source {source_id} ingested successfully.")
    except Exception as exc:
        source_update_status(source_id, "failed")
        print(f"[ADMIN ERROR] Source {source_id} ingestion failed: {exc}")


def _ingest_private_source(
    tenant_id: str,
    file_path: str,
    filename: str,
    source_id: int,
    subject_id: int,
    owner_id: int,
):
    """
    Background task: ingest a student file with private provenance metadata,
    then flip the source status to 'ready' (or 'failed').
    """
    try:
        ingest_file(
            tenant_id,
            file_path,
            filename,
            source_id=source_id,
            subject_id=subject_id,
            owner_id=owner_id,
            visibility="private",
        )
        source_update_status(source_id, "ready")
        print(f"[STUDENT] Source {source_id} ingested successfully.")
    except Exception as exc:
        source_update_status(source_id, "failed")
        print(f"[STUDENT ERROR] Source {source_id} ingestion failed: {exc}")


@router.post("/admin/subjects/{subject_id}/sources/upload", status_code=201)
async def admin_upload_source(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
    _user: dict = Depends(require_admin),
):
    """
    Admin endpoint: upload a file as a global source under a subject.
    """
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    files_dir = os.path.join(DATA_DIR, tenant_id, "files", "subjects", str(subject_id))
    os.makedirs(files_dir, exist_ok=True)
    file_path = os.path.join(files_dir, file.filename)
    async with aiofiles.open(file_path, "wb") as buf:
        while chunk := await file.read(1024 * 1024):
            await buf.write(chunk)

    source = source_create(
        subject_id=subject_id,
        title=file.filename,
        file_ref=file_path,
        owner_id=None,
        visibility="global",
        status="pending",
    )

    background_tasks.add_task(
        _ingest_global_source,
        tenant_id,
        file_path,
        file.filename,
        source["id"],
        subject_id,
    )

    return {
        "source_id":   source["id"],
        "subject_id":  subject_id,
        "title":       file.filename,
        "visibility":  "global",
        "owner_id":    None,
        "status":      "pending",
        "message":     "File accepted; ingestion running in background.",
    }


@router.post("/subjects/{subject_id}/sources/upload", status_code=201)
async def student_upload_source(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    """
    Student endpoint: upload a private file under a subject.
    """
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User account has no tenant assigned.")

    files_dir = os.path.join(DATA_DIR, tenant_id, "files", "subjects", str(subject_id))
    os.makedirs(files_dir, exist_ok=True)
    file_path = os.path.join(files_dir, file.filename)
    async with aiofiles.open(file_path, "wb") as buf:
        while chunk := await file.read(1024 * 1024):
            await buf.write(chunk)

    source = source_create(
        subject_id=subject_id,
        title=file.filename,
        file_ref=file_path,
        owner_id=user["id"],
        visibility="private",
        status="pending",
    )

    background_tasks.add_task(
        _ingest_private_source,
        tenant_id,
        file_path,
        file.filename,
        source["id"],
        subject_id,
        user["id"],
    )

    return {
        "source_id":  source["id"],
        "subject_id": subject_id,
        "title":      file.filename,
        "visibility": "private",
        "owner_id":   user["id"],
        "status":     "pending",
        "message":    "File accepted; ingestion running in background.",
    }


@router.get("/subjects/{subject_id}/sources")
async def student_list_sources(
    subject_id: int,
):
    """
    List all sources for a given subject.
    No authentication required for read access.
    """
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    
    return source_list_by_subject(subject_id)
