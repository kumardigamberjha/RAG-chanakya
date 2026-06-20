# System dependencies: sudo apt install poppler-utils
# Python dependencies: pip install pdf2image

import os
import shutil
import sys
import base64
import io
from PIL import Image
import pdf2image
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import requests
import json
from typing import Any, List, Optional, Dict, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, AIMessageChunk
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk

# Load environment variables
load_dotenv()

# Ensure local dummy packages are found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class NvidiaMinimaxChat(BaseChatModel):
    model_name: str = "minimaxai/minimax-m3"
    nvidia_api_key: str = ""
    temperature: float = 1.0
    top_p: float = 0.95
    max_tokens: int = 8192

    @property
    def _llm_type(self) -> str:
        return "nvidia-minimax"

    def _format_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        formatted_messages = []
        system_content = ""
        for msg in messages:
            content = msg.content if msg.content else ""
            if not isinstance(content, str):
                content = str(content)
                
            if isinstance(msg, SystemMessage):
                system_content += content + "\n"
            elif isinstance(msg, HumanMessage):
                if system_content:
                    formatted_messages.append({"role": "user", "content": f"{system_content.strip()}\n\n{content}"})
                    system_content = ""
                else:
                    formatted_messages.append({"role": "user", "content": content or " "})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": content or " "})
            else:
                if system_content:
                    formatted_messages.append({"role": "user", "content": f"{system_content.strip()}\n\n{content}"})
                    system_content = ""
                else:
                    formatted_messages.append({"role": "user", "content": content or " "})
        
        if system_content and not formatted_messages:
            formatted_messages.append({"role": "user", "content": system_content.strip()})
            
        return formatted_messages

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        headers = {
            "Authorization": f"Bearer {self.nvidia_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        formatted_messages = self._format_messages(messages)

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False
        }

        response = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        res_data = response.json()
        
        content = res_data["choices"][0]["message"]["content"]
        ai_msg = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        headers = {
            "Authorization": f"Bearer {self.nvidia_api_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json"
        }
        
        formatted_messages = self._format_messages(messages)

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": True
        }

        response = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("data:"):
                data_content = line_str[5:].strip()
                if data_content == "[DONE]":
                    break
                try:
                    chunk_json = json.loads(data_content)
                    delta = chunk_json["choices"][0]["delta"]
                    if "content" in delta:
                        content_chunk = delta["content"]
                        yield ChatGenerationChunk(message=AIMessageChunk(content=content_chunk))
                except Exception as e:
                    print(f"Error parsing Nvidia chunk: {e}")

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, BSHTMLLoader
from langchain_ollama import ChatOllama
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
try:
    from langchain.chains import create_retrieval_chain, create_history_aware_retriever
    from langchain.chains.combine_documents import create_stuff_documents_chain
except ImportError:
    from langchain_classic.chains import create_retrieval_chain, create_history_aware_retriever
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document


# Initialize models
ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

try:
    embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
except Exception as e:
    print(f"Error loading embeddings: {e}")
    embeddings_model = None

try:
    # Enabled streaming for real-time interaction
    # Default is Gemma with Mistral fallback
    gemma_llm = ChatOllama(model="gemma4:31b-cloud", base_url=ollama_base_url, streaming=True)
    mistral_llm = ChatOllama(model="mistral:latest", base_url=ollama_base_url, streaming=True)
    llm = gemma_llm.with_fallbacks([mistral_llm])
except Exception as e:
    print(f"Error loading LLM: {e}")
    llm = None

def get_llm_by_id(model_id=None):
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")

    if model_id == "minimax_nvidia":
        if not nvidia_key or nvidia_key == "your_nvidia_api_key_here":
            raise ValueError("NVIDIA_API_KEY is not configured in backend .env file.")
        return NvidiaMinimaxChat(nvidia_api_key=nvidia_key)
    
    elif model_id == "mistral_ollama":
        return ChatOllama(model="mistral:latest", base_url=ollama_base_url, streaming=True)
        
    elif model_id == "gemma_ollama":
        gemma_llm = ChatOllama(model="gemma4:31b-cloud", base_url=ollama_base_url, streaming=True)
        mistral_llm = ChatOllama(model="mistral:latest", base_url=ollama_base_url, streaming=True)
        return gemma_llm.with_fallbacks([mistral_llm])
        
    else:
        return llm

# Global BGE Reranker (Loaded once into VRAM for performance)
try:
    print("[SYSTEM] Pre-loading BGE GPU Reranker into VRAM...")
    bge_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base", model_kwargs={"device": "cuda"})
    global_compressor = CrossEncoderReranker(model=bge_model, top_n=8)
except Exception as e:
    print(f"Error pre-loading reranker: {e}")
    bge_model = None
    global_compressor = None

DB_PATH = "chroma_db"

def get_vector_db(tenant_id):
    """Get the Chroma collection for a specific tenant"""
    return Chroma(
        collection_name=tenant_id,
        embedding_function=embeddings_model,
        persist_directory=DB_PATH
    )

def process_ocr_page(img, page_num, vision_llm, original_filename, tenant_id,
                     source_id=None, subject_id=None, owner_id=None, visibility=None):
    """Helper function to process a single page for OCR in parallel"""
    try:
        # Optimization: Pass size to convert_from_path to resize DURING rendering
        # This is much faster than resizing in Python later.
        # 800px width is plenty for the model to read text.
        max_dim = 800
        if max(img.size) > max_dim:
             # Just in case, though convert_from_path should handle it
             img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        
        # Convert to compressed JPEG with lower quality to minimize payload
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=70)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        prompt = "Extract all the readable text from this image. Output ONLY the extracted text. Do not add any commentary, markdown formatting, or conversational filler."
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_str}"},
            ]
        )
        
        response = vision_llm.invoke([message])
        text = response.content.strip()
        
        if text:
            return Document(
                page_content=text,
                metadata={
                    "source":      original_filename,
                    "source_file": original_filename,
                    "tenant_id":   tenant_id,
                    "page_number": page_num,
                    # ── provenance fields ──────────────────────────────────
                    "source_id":   source_id,
                    "subject_id":  subject_id,
                    "owner_id":    owner_id,
                    "visibility":  visibility,
                }
            )
    except Exception as e:
        print(f"[ERROR] Page {page_num} OCR failed: {e}")
    return None

def ingest_file(
    tenant_id: str,
    file_path: str,
    original_filename: str,
    *,
    source_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    visibility: Optional[str] = None,
):
    """
    Load a file, chunk it, and add to the tenant's Chroma collection.

    Provenance kwargs (all optional – safe to omit for legacy callers):
        source_id   – FK to sources.id
        subject_id  – FK to subjects.id
        owner_id    – FK to users.id  (nullable)
        visibility  – 'global' | 'private'

    All four fields are stamped onto every chunk's Chroma metadata so that
    future retrieval filters can use them.
    """
    ext = os.path.splitext(original_filename)[1].lower()
    docs = []

    # ── Common provenance dict injected into every Document ────────────────
    provenance = {
        "source_id":  source_id,
        "subject_id": subject_id,
        "owner_id":   owner_id,
        "visibility": visibility,
    }
    
    if ext == '.pdf':
        print(f"[SYSTEM] Background OCR active for: {original_filename}")
        try:
            print(f"[SYSTEM] Step 1: Rendering PDF to images (this may take a moment)...")
            # Added thread_count=4 and size=(800, None) for max speed
            images = pdf2image.convert_from_path(file_path, thread_count=4, size=(800, None))
            gemma_vision = ChatOllama(model="gemma4:31b-cloud", base_url=ollama_base_url)
            mistral_vision = ChatOllama(model="mistral:latest", base_url=ollama_base_url)
            vision_llm = gemma_vision.with_fallbacks([mistral_vision])
            
            # Increased max_workers for parallel ingestion
            print(f"[SYSTEM] Step 2: Processing {len(images)} pages via Vision OCR...")
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [
                    executor.submit(
                        process_ocr_page, img, i+1, vision_llm,
                        original_filename, tenant_id,
                        source_id, subject_id, owner_id, visibility,
                    )
                    for i, img in enumerate(images)
                ]
                for future in futures:
                    doc = future.result()
                    if doc:
                        docs.append(doc)
                        
        except Exception as e:
            print(f"[ERROR] Parallel OCR failed: {e}")
            raise ValueError(f"OCR failed for {original_filename}: {str(e)}")
            
    elif ext in ['.txt', '.md', '.html', '.htm']:
        if ext in ['.txt', '.md']:
            loader = TextLoader(file_path)
        else:
            loader = BSHTMLLoader(file_path)
        docs = loader.load()
        # Inject metadata for standard files
        for doc in docs:
            doc.metadata.update({
                "source":      original_filename,
                "source_file": original_filename,
                "tenant_id":   tenant_id,
                **provenance,
            })
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Defensive Guardrail: Verify docs list is not empty and contains actual text
    if not docs or not any(doc.page_content.strip() for doc in docs):
        print(f"[ERROR] No text content found for {file_path}")
        raise ValueError(f"Could not extract any readable text from {original_filename}. The file might be empty, corrupted, or the OCR failed to read the content.")
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    
    # Defensive Guardrail: Verify splits before ChromaDB insertion
    if not chunks:
        print(f"[ERROR] Text splitting resulted in 0 chunks for {file_path}")
        raise ValueError(f"No text chunks were created from {original_filename}. Text splitting failed.")

    # ── Stamp provenance onto every chunk (covers PDF path too) ────────────
    for chunk in chunks:
        chunk.metadata.update(provenance)

    print(f"[SYSTEM] Ingesting {len(chunks)} chunks into collection: {tenant_id}")
    db = get_vector_db(tenant_id)
    db.add_documents(chunks)
    return len(chunks)

def remove_file_from_db(tenant_id, original_filename):
    """Remove a specific file's chunks from the tenant's Chroma collection"""
    db = get_vector_db(tenant_id)

    # Chroma supports deleting by metadata
    # We retrieve the ids first to delete them
    try:
        collection = db._collection
        res = collection.get(where={"source": original_filename})
        if res and res['ids']:
            collection.delete(ids=res['ids'])
            print(f"Deleted {len(res['ids'])} chunks for {original_filename} in tenant {tenant_id}")
            return True
    except Exception as e:
        print(f"Error removing file from DB: {e}")
    return False


def remove_source_from_vector_db(tenant_id: str, source_id: int) -> int:
    """
    Delete all chunks tagged with source_id from the tenant's Chroma collection.
    Returns the number of chunks deleted (0 if none found or on error).
    """
    db = get_vector_db(tenant_id)
    try:
        collection = db._collection
        res = collection.get(where={"source_id": {"$eq": source_id}})
        if res and res["ids"]:
            collection.delete(ids=res["ids"])
            print(f"[VECTOR] Deleted {len(res['ids'])} chunks for source_id={source_id}")
            return len(res["ids"])
    except Exception as exc:
        print(f"[VECTOR ERROR] Failed to delete source_id={source_id}: {exc}")
    return 0

def build_retrieval_filter(
    subject_id: Optional[int] = None,
    current_user_id: Optional[int] = None,
) -> Optional[dict]:
    """
    Build a ChromaDB ``where`` filter that enforces:

        subject_id == subject_id
        AND (visibility == 'global' OR owner_id == current_user_id)

    Rules:
    - Returns ``None`` when *subject_id* is ``None``  → no filter, legacy behaviour.
    - When *current_user_id* is ``None`` (unauthenticated) only global docs are returned.

    ChromaDB operator reference:
        https://docs.trychroma.com/docs/querying-collections/filtering
    """
    if subject_id is None:
        return None

    # Ownership clause: caller sees global docs + their own private docs
    if current_user_id is not None:
        ownership: dict = {
            "$or": [
                {"visibility": {"$eq": "global"}},
                {"owner_id":   {"$eq": current_user_id}},
            ]
        }
    else:
        # Unauthenticated → global only
        ownership = {"visibility": {"$eq": "global"}}

    return {
        "$and": [
            {"subject_id": {"$eq": subject_id}},
            ownership,
        ]
    }


def get_rag_chain(
    tenant_id: str,
    model_id: Optional[str] = None,
    subject_id: Optional[int] = None,
    current_user_id: Optional[int] = None,
    legacy_filenames: Optional[List[str]] = None,
):
    """
    Create the history-aware RAG chain for a specific tenant.

    Args:
        tenant_id:       Chroma collection name (school / institute).
        model_id:        LLM selector string passed to get_llm_by_id().
        subject_id:      When provided, restricts retrieval to this subject.
        current_user_id: Used to allow the caller's own private documents
                         through alongside global ones.
    """
    db = get_vector_db(tenant_id)

    # 1. Build provenance-aware search kwargs
    where_filter = build_retrieval_filter(subject_id, current_user_id)
    search_kwargs: dict = {"k": 30}
    if where_filter is not None:
        search_kwargs["filter"] = where_filter
        print(f"[SYSTEM] Retrieval filter active: subject_id={subject_id}, user_id={current_user_id}")
    elif legacy_filenames is not None and len(legacy_filenames) > 0:
        # If no subject is selected, but we have legacy files (Chanakya Neeti), restrict to those legacy files
        search_kwargs["filter"] = {"source": {"$in": legacy_filenames}}
        print(f"[SYSTEM] Legacy retrieval filter active for {len(legacy_filenames)} files")

    # 2. Base Retriever (Chroma DB)
    base_retriever = db.as_retriever(search_kwargs=search_kwargs)
    
    # 2. BGE GPU RERANKER (HuggingFaceCrossEncoder)
    try:
        from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
        
        if global_compressor:
            retriever = ContextualCompressionRetriever(
                base_compressor=global_compressor,
                base_retriever=base_retriever
            )
            print("[SYSTEM] Using global BGE GPU Reranker.")
        else:
            print("[SYSTEM] Global reranker unavailable, using standard retriever.")
            retriever = base_retriever
    except Exception as e:
        print(f"Reranker retrieval failed: {e}, using standard retriever.")
        retriever = base_retriever
    
    # Resolve the LLM to use
    selected_llm = get_llm_by_id(model_id)
    print(f"[SYSTEM] RAG chain is using model ID: {model_id or 'gemma_ollama (default)'}")
    if not selected_llm:
        raise ValueError("Model could not be initialized.")
        
    # Reformulate question prompt
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. CRITICAL: If the user asks a multi-part question, you MUST preserve all distinct parts of their inquiry in your standalone question so the vector database searches for all concepts. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    history_aware_retriever = create_history_aware_retriever(
        selected_llm, retriever, contextualize_q_prompt
    )
    
    # Answer generation prompt
    qa_system_prompt = (
        "You are an insightful, Socratic Teacher. Your goal is to guide the student using thought-provoking questions and clear synthesis of the text.\n\n"
        "STRICT RULES:\n"
        "1. Base your response heavily on the provided syllabus CONTEXT below AND the established facts in the CHAT HISTORY.\n"
        "2. Address multi-part questions comprehensively. If the user asks two distinct things, answer both.\n"
        "3. If a specific concept is missing from the CONTEXT, but was already established in the immediate CHAT HISTORY, you may use the history to answer.\n"
        "4. Only if the query is completely unanswerable from both the CONTEXT and the CHAT HISTORY, reply exactly with: 'This concept is not covered in your uploaded texts.'\n"
        "5. Cite your sources based on the context metadata.\n\n"
        "CONTEXT:\n{context}"
    )
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    question_answer_chain = create_stuff_documents_chain(selected_llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    return rag_chain

def generate_suggestions(tenant_id: str) -> List[str]:
    """Queries Chroma DB for document snippets and prompts the LLM to generate 3 specific suggested questions."""
    try:
        db = get_vector_db(tenant_id)
        collection = db._collection
        res = collection.get(limit=5)
        if not res or not res.get("documents"):
            print(f"[SYSTEM] No documents found in Chroma collection for tenant: {tenant_id}")
            return []
        
        context_text = "\n\n".join(res["documents"])
        llm_instance = get_llm_by_id()
        if not llm_instance:
            print("[SYSTEM] LLM instance could not be loaded for suggestions.")
            return []
            
        prompt = (
            "You are a helpful assistant. Based on the following source document text, "
            "generate exactly 3 distinct, specific, and interesting questions that a reader/student "
            "would ask about the text. The questions must be direct, clear, and refer to specific details in the text "
            "(do NOT ask generic questions like 'what is this document about').\n\n"
            "Format the output as a valid JSON list of strings, like this:\n"
            "[\n  \"Question 1?\",\n  \"Question 2?\",\n  \"Question 3?\"\n]\n"
            "Return ONLY the JSON list. Do not include markdown formatting or extra text.\n\n"
            f"TEXT CONTEXT:\n{context_text}"
        )
        
        response = llm_instance.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean markdown code blocks if present
        content = content.replace("```json", "").replace("```", "").strip()
        
        # Try JSON parsing
        start_idx = content.find("[")
        end_idx = content.rfind("]")
        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx+1]
            try:
                suggestions = json.loads(json_str)
                if isinstance(suggestions, list) and len(suggestions) > 0:
                    return [str(s).strip() for s in suggestions[:3]]
            except Exception as json_err:
                print(f"[SYSTEM] JSON parse failed on extracted string: {json_err}")
        
        # Fallback line-by-line parsing
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        extracted = []
        for line in lines:
            cleaned = line
            if cleaned.startswith("-") or cleaned.startswith("*"):
                cleaned = cleaned[1:].strip()
            elif any(cleaned.startswith(f"{i}.") for i in range(1, 10)):
                cleaned = cleaned[2:].strip()
            cleaned = cleaned.strip('"').strip("'").strip()
            if cleaned.endswith("?"):
                extracted.append(cleaned)
        if len(extracted) >= 3:
            return extracted[:3]
            
    except Exception as e:
        print(f"Error generating suggestions: {e}")
    return []


