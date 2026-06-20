import os
import json
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from authentication.auth import get_current_tenant, get_optional_user
from chat.crud import (
    get_db_chats,
    create_db_chat,
    rename_db_chat,
    delete_db_chat,
    get_db_chat_history,
    append_db_message
)
from chat.rag_backend import (
    ingest_file, remove_file_from_db, get_rag_chain,
    get_llm_by_id, generate_suggestions, get_vector_db, build_retrieval_filter
)

router = APIRouter(prefix="/api", tags=["chat"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_data")
TENANTS_METADATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tenants.json")

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

@router.post("/tenant/upload")
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

@router.delete("/tenant/files/{filename}")
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

@router.get("/tenant/files")
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

@router.get("/tenant/suggestions")
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

@router.get("/chats")
async def get_chats(tenant_id: str = Depends(get_current_tenant)):
    return get_db_chats(tenant_id)

@router.post("/chats")
async def create_chat(
    chat: ChatCreate, 
    tenant_id: str = Depends(get_current_tenant)
):
    chat_id = str(uuid.uuid4())
    new_chat = create_db_chat(chat_id, chat.name, tenant_id)
    return new_chat

@router.patch("/chats/{chat_id}")
async def rename_chat(
    chat_id: str,
    chat_update: ChatUpdate,
    tenant_id: str = Depends(get_current_tenant)
):
    updated_chat = rename_db_chat(chat_id, chat_update.name, tenant_id)
    if not updated_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return updated_chat

@router.delete("/chats/{chat_id}")
async def delete_chat(
    chat_id: str,
    tenant_id: str = Depends(get_current_tenant)
):
    success = delete_db_chat(chat_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success"}

@router.get("/chats/{chat_id}/history")
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

@router.get("/models")
async def get_models():
    """Retrieve list of available LLM models"""
    return [
        {"id": "gemma_ollama", "name": "Gemma 31B", "description": "gemma4:31b-cloud (mistral backup)"},
        {"id": "mistral_ollama", "name": "Mistral Latest", "description": "mistral:latest"},
        {"id": "minimax_nvidia", "name": "MiniMax-M3 (Nvidia)", "description": "minimaxai/minimax-m3 via Nvidia API"}
    ]

@router.post("/chats/{chat_id}/query")
async def query_chat(
    chat_id: str,
    request: QueryRequest,
    tenant_id: str = Depends(get_current_tenant),
    current_user: Optional[dict] = Depends(get_optional_user),
):
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
                    res = collection.get(limit=50)
                        
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
Do NOT provide the answers immediately after each question. Put the answer key at the very end in a separate section starting EXACTLY with the heading "### Answer Key".

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
                    legacy_filenames=None,
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
