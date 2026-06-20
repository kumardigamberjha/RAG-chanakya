from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import json
import shutil
import aiofiles
from datetime import datetime, timezone
from langchain_core.messages import SystemMessage
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from rag_backend import ingest_file, remove_file_from_db, remove_source_from_vector_db, get_rag_chain, get_llm_by_id, generate_suggestions, get_vector_db, build_retrieval_filter
from langchain_core.messages import HumanMessage, AIMessage
from database import (
    init_db,
    get_db_chats,
    create_db_chat,
    rename_db_chat,
    delete_db_chat,
    get_db_chat_history,
    append_db_message
)
from auth import (
    verify_password,
    create_access_token,
    get_user_by_credential,
    require_auth,
    require_admin,
    get_optional_user,
)
from crud import (
    subject_list,
    subject_create,
    subject_get,
    subject_delete,
    source_create,
    source_get,
    source_delete,
    source_update_status,
    source_list_by_subject,
    source_list_for_user,
)

app = FastAPI(title="Wings of AI - B2B RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

# --- DB Paths ---
# We now separate metadata into Tenant data (files) and Chat data (user sessions)
TENANTS_METADATA_FILE = "tenants.json"
DATA_DIR = "app_data"

os.makedirs(DATA_DIR, exist_ok=True)


@app.get("/api/debug-users")
async def debug_users():
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "chats.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, password_hash, role, tenant_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "email": r[2], "password_hash": r[3], "role": r[4], "tenant_id": r[5]} for r in rows]

class LoginRequest(BaseModel):
    """Body for POST /api/auth/login."""
    login: str    # accepts username OR email
    password: str


@app.post("/api/auth/login", tags=["auth"])
async def login(body: LoginRequest):
    """
    Exchange credentials for a signed JWT.

    - **login**: username or email address
    - **password**: plain-text password

    Returns ``{"access_token": "<jwt>", "token_type": "bearer", "role": "<role>"}``.
    Raises **401** on invalid credentials.
    """
    try:
        from seed import seed as run_seed, seed_students as run_seed_students
        run_seed()
        run_seed_students()
    except Exception as exc:
        print(f"[login hook] seeding failed: {exc}")

    user = get_user_by_credential(body.login)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


# ==========================================
# 1-A. SUBJECTS API
# ==========================================

class SubjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


@app.get("/api/subjects", tags=["subjects"])
async def list_subjects(user: Optional[dict] = Depends(get_optional_user)):
    """
    List all subjects.  Anyone may call this to filter chat queries.
    """
    return subject_list()


@app.post("/api/subjects", status_code=201, tags=["subjects"])
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


@app.delete("/api/subjects/{subject_id}", status_code=200, tags=["subjects"])
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


# --- Security Dependency ---
def get_current_tenant(x_tenant_id: str = Header(..., description="School/Institute ID")):
    """Ensures every request is strictly isolated to a specific school."""
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="Missing X-Tenant-ID Header")
    return x_tenant_id


@app.get("/api/admin/subjects/{subject_id}/sources")
async def admin_list_sources(
    subject_id: int,
    _user: dict = Depends(require_admin),
):
    """List all sources for a subject (admin only)."""
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return source_list_by_subject(subject_id)


@app.delete("/api/admin/subjects/{subject_id}/sources/{source_id}", status_code=200)
async def admin_delete_source(
    subject_id: int,
    source_id: int,
    tenant_id: str = Depends(get_current_tenant),
    _user: dict = Depends(require_admin),
):
    """
    Admin endpoint: remove a source and purge its chunks from the vector store.

    Deletion order:
      1. Verify source exists and belongs to this subject.
      2. Delete all chunks from ChromaDB (by source_id metadata filter).
      3. Delete the physical file from disk (best-effort).
      4. Delete the sources row from SQLite.
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


@app.post("/api/admin/subjects/{subject_id}/sources/upload", status_code=201)
async def admin_upload_source(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
    _user: dict = Depends(require_admin),
):
    """
    Admin endpoint: upload a file as a global source under a subject.

    • Creates a sources row with visibility='global', owner_id=NULL.
    • Saves the file to disk.
    • Triggers ingest_file() in the background with the correct provenance
      so every chunk is tagged with source_id, subject_id, visibility='global'.
    """
    subject = subject_get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    # 1. Persist the file
    files_dir = os.path.join(DATA_DIR, tenant_id, "files", "subjects", str(subject_id))
    os.makedirs(files_dir, exist_ok=True)
    file_path = os.path.join(files_dir, file.filename)
    async with aiofiles.open(file_path, "wb") as buf:
        while chunk := await file.read(1024 * 1024):
            await buf.write(chunk)

    # 2. Register in sources table
    source = source_create(
        subject_id=subject_id,
        title=file.filename,
        file_ref=file_path,
        owner_id=None,
        visibility="global",
        status="pending",
    )

    # 3. Ingest in the background
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

# ==========================================
# 1-B. STUDENT SOURCES API
# ==========================================

@app.post("/api/subjects/{subject_id}/sources/upload", status_code=201, tags=["sources"])
async def student_upload_source(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    """
    Student endpoint: upload a private file under a subject.

    • Creates a sources row with visibility='private', owner_id=current user.
    • Saves the file to disk under the user's tenant data directory.
    • Triggers ingest_file() in the background.
    • tenant_id is taken from the JWT — students cannot forge a different tenant.
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


@app.get("/api/subjects/{subject_id}/sources", tags=["sources"])
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


class ChatCreate(BaseModel):
    name: str

class ChatUpdate(BaseModel):
    name: str

class QueryRequest(BaseModel):
    query: str
    model: Optional[str] = None
    subject_id: Optional[int] = None   # when set, scope retrieval to this subject
    is_quiz: bool = False

# --- Metadata Helpers ---
def load_metadata(filepath):
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_metadata(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)


# ==========================================
# 1. TEACHER PORTAL: KNOWLEDGE BASE API
# ==========================================

def ingest_and_update_suggestions(
    tenant_id: str,
    file_path: str,
    filename: str,
    *,
    source_id=None,
    subject_id=None,
    owner_id=None,
    visibility=None,
):
    """Background task to ingest the file and then update/cache suggestions in tenants.json."""
    try:
        ingest_file(
            tenant_id, file_path, filename,
            source_id=source_id,
            subject_id=subject_id,
            owner_id=owner_id,
            visibility=visibility,
        )
        suggestions = generate_suggestions(tenant_id)
        if suggestions:
            tenants = load_metadata(TENANTS_METADATA_FILE)
            if tenant_id not in tenants:
                tenants[tenant_id] = {"files": []}
            tenants[tenant_id]["suggestions"] = suggestions
            save_metadata(TENANTS_METADATA_FILE, tenants)
            print(f"[BACKGROUND] Generated suggestions for tenant {tenant_id}: {suggestions}")
    except Exception as e:
        print(f"[BACKGROUND ERROR] Ingestion/Suggestions background task failed: {e}")

@app.post("/api/tenant/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    tenant_id: str = Depends(get_current_tenant)
):
    """Teachers upload syllabus here. Ingestion runs in the background."""
    tenants = load_metadata(TENANTS_METADATA_FILE)
    if tenant_id not in tenants:
        tenants[tenant_id] = {"files": []}
    
    files_dir = os.path.join(DATA_DIR, tenant_id, "files")
    os.makedirs(files_dir, exist_ok=True)
    
    file_path = os.path.join(files_dir, file.filename)
    async with aiofiles.open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024): # 1MB chunks
            await buffer.write(chunk)
    
    # Run ingestion and suggestion generation in the background
    background_tasks.add_task(ingest_and_update_suggestions, tenant_id, file_path, file.filename)
    
    if file.filename not in tenants[tenant_id]["files"]:
        tenants[tenant_id]["files"].append(file.filename)
        save_metadata(TENANTS_METADATA_FILE, tenants)
        
    return {"filename": file.filename, "status": "processing"}

@app.delete("/api/tenant/files/{filename}")
async def delete_file(
    filename: str, 
    tenant_id: str = Depends(get_current_tenant)
):
    tenants = load_metadata(TENANTS_METADATA_FILE)
    if tenant_id in tenants and filename in tenants[tenant_id]["files"]:
        remove_file_from_db(tenant_id, filename)
        tenants[tenant_id]["files"].remove(filename)
        
        file_path = os.path.join(DATA_DIR, tenant_id, "files", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # Re-generate suggestions from remaining files
        if tenants[tenant_id]["files"]:
            suggestions = generate_suggestions(tenant_id)
            tenants[tenant_id]["suggestions"] = suggestions
        else:
            tenants[tenant_id]["suggestions"] = []
            
        save_metadata(TENANTS_METADATA_FILE, tenants)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/tenant/files")
async def list_files(tenant_id: str = Depends(get_current_tenant)):
    tenants = load_metadata(TENANTS_METADATA_FILE)
    if tenant_id in tenants:
        return tenants[tenant_id].get("files", [])
    return []

DEFAULT_SUGGESTIONS = [
    "Summarize the key principles discussed in the document.",
    "What are the most important lessons or takeaways?",
    "Can you provide an overview of the main topics covered?"
]

@app.get("/api/tenant/suggestions")
async def get_tenant_suggestions(tenant_id: str = Depends(get_current_tenant)):
    """Retrieve cached suggestions or generate them if documents exist."""
    tenants = load_metadata(TENANTS_METADATA_FILE)
    if tenant_id in tenants:
        suggestions = tenants[tenant_id].get("suggestions")
        if suggestions and len(suggestions) >= 3:
            return suggestions
            
    # Fallback: if files exist but suggestions are not generated yet, do it now
    if tenant_id in tenants and tenants[tenant_id].get("files"):
        suggestions = generate_suggestions(tenant_id)
        if suggestions:
            tenants[tenant_id]["suggestions"] = suggestions
            save_metadata(TENANTS_METADATA_FILE, tenants)
            return suggestions
            
    return DEFAULT_SUGGESTIONS



# ==========================================
# 2. STUDENT PORTAL: SESSION & QUERY API
# ==========================================

@app.get("/api/chats")
async def get_chats(tenant_id: str = Depends(get_current_tenant)):
    return get_db_chats(tenant_id)

@app.post("/api/chats")
async def create_chat(
    chat: ChatCreate, 
    tenant_id: str = Depends(get_current_tenant)
):
    chat_id = str(uuid.uuid4())
    new_chat = create_db_chat(chat_id, chat.name, tenant_id)
    return new_chat

@app.patch("/api/chats/{chat_id}")
async def rename_chat(
    chat_id: str,
    chat_update: ChatUpdate,
    tenant_id: str = Depends(get_current_tenant)
):
    updated_chat = rename_db_chat(chat_id, chat_update.name, tenant_id)
    if not updated_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return updated_chat

@app.delete("/api/chats/{chat_id}")
async def delete_chat(
    chat_id: str,
    tenant_id: str = Depends(get_current_tenant)
):
    success = delete_db_chat(chat_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success"}

@app.get("/api/chats/{chat_id}/history")
async def get_history(
    chat_id: str, 
    tenant_id: str = Depends(get_current_tenant)
):
    history = get_db_chat_history(chat_id)
    formatted_history = []
    for msg in history:
        msg_type = "human" if isinstance(msg, HumanMessage) else "ai"
        item = {"type": msg_type, "content": msg.content}
        if msg_type == "ai":
            item["sources"] = getattr(msg, 'metadata_sources', msg.additional_kwargs.get("sources", []))
        formatted_history.append(item)
    return formatted_history

from fastapi.responses import StreamingResponse

@app.get("/api/models")
async def get_models():
    """Retrieve list of available LLM models"""
    return [
        {"id": "gemma_ollama", "name": "Gemma 31B", "description": "gemma4:31b-cloud (mistral backup)"},
        {"id": "mistral_ollama", "name": "Mistral Latest", "description": "mistral:latest"},
        {"id": "minimax_nvidia", "name": "MiniMax-M3 (Nvidia)", "description": "minimaxai/minimax-m3 via Nvidia API"}
    ]

@app.post("/api/chats/{chat_id}/query")
async def query_chat(
    chat_id: str,
    request: QueryRequest,
    tenant_id: str = Depends(get_current_tenant),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    tenants = load_metadata(TENANTS_METADATA_FILE)
    if tenant_id not in tenants or not tenants[tenant_id]["files"]:
        return {"answer": "Your teacher hasn't uploaded the syllabus yet.", "sources": []}
    
    history = get_db_chat_history(chat_id)
    is_first_message = len(history) == 0
    new_title = None
    
    selected_llm = get_llm_by_id(request.model)
    
    if is_first_message:
        try:
            title_prompt = [
                SystemMessage(content="You are a helpful assistant. Summarize the user's question into a short, concise title (2 to 5 words). Do not use any introductory phrase, quotes, or punctuation. Output ONLY the title itself."),
                HumanMessage(content=request.query)
            ]
            title_response = selected_llm.invoke(title_prompt)
            title_candidate = title_response.content.strip()
            title_candidate = title_candidate.replace('"', '').replace("'", "").strip()
            if title_candidate and len(title_candidate) <= 60:
                new_title = title_candidate
            else:
                new_title = request.query[:40] + "..." if len(request.query) > 40 else request.query
        except Exception as e:
            print(f"Error generating chat title: {e}")
            new_title = request.query[:40] + "..." if len(request.query) > 40 else request.query
            
        if new_title:
            rename_db_chat(chat_id, new_title, tenant_id)

    async def event_generator():
        full_answer = ""
        sources = []
        try:
            # Yield new title event first if available
            if new_title:
                yield f"data: {json.dumps({'title': new_title})}\n\n"
                
            if request.is_quiz:
                # Custom Quiz Generation Logic
                db = get_vector_db(tenant_id)
                collection = db._collection
                where_filter = build_retrieval_filter(request.subject_id, current_user["id"] if current_user else None)
                
                # Fetch chunks from Chroma
                if where_filter:
                    res = collection.get(where=where_filter, limit=50)
                else:
                    if tenants[tenant_id]["files"]:
                        res = collection.get(where={"source": {"$in": tenants[tenant_id]["files"]}}, limit=50)
                    else:
                        res = {"documents": []}
                        
                import random
                docs = res.get("documents", [])
                if docs:
                    sampled_docs = random.sample(docs, min(10, len(docs)))
                    context = "\n\n".join(sampled_docs)
                else:
                    context = "No documents found for the selected subject."

                prompt = f"""You are an expert teacher. Based on the following excerpts, generate a 5-question multiple-choice quiz.
The quiz should range from beginner level to experienced level questions.
For each question, provide exactly 4 options (A, B, C, D).
Do NOT provide the answers immediately after each question. Put the answer key at the very end in a separate section.

Excerpts:
{context}"""
                messages_for_llm = [SystemMessage(content="You are an expert quiz generator."), HumanMessage(content=prompt)]
                
                async for chunk in selected_llm.astream(messages_for_llm):
                    token = chunk.content
                    full_answer += token
                    yield f"data: {json.dumps({'chunk': token})}\n\n"
                    
                yield f"data: {json.dumps({'sources': []})}\n\n"

            else:
                rag_chain = get_rag_chain(
                    tenant_id,
                    model_id=request.model,
                    subject_id=request.subject_id,
                    current_user_id=current_user["id"] if current_user else None,
                    legacy_filenames=tenants[tenant_id]["files"],
                )
                # Use astream for real-time token generation
                async for chunk in rag_chain.astream({"input": request.query, "chat_history": history}):
                    # Retrieve answer tokens
                    if "answer" in chunk:
                        token = chunk["answer"]
                        full_answer += token
                        yield f"data: {json.dumps({'chunk': token})}\n\n"
                    
                    # Retrieve context documents (usually comes at the start or end)
                    if "context" in chunk:
                        sources = chunk["context"]
            
            if not request.is_quiz:
                # Send source citations as the final event
                formatted_sources = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in sources]
                yield f"data: {json.dumps({'sources': formatted_sources})}\n\n"
            else:
                formatted_sources = []
            
            # Persist the conversation to SQLite
            append_db_message(chat_id, "human", request.query)
            append_db_message(chat_id, "ai", full_answer, formatted_sources)
            
        except Exception as e:
            print(f"Streaming Error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)