# Wings of AI: Subject-Centric Educational RAG Platform

This project is a deeply local, privacy-first Retrieval-Augmented Generation (RAG) system built to serve as an interactive, subject-specific educational platform. It features a complete pipeline from ingesting documents (like "Chanakya Neeti" or custom syllabus PDFs) to creating a context-aware conversational AI. 

The system has evolved into a robust architecture, supporting a production-ready FastAPI + React ecosystem designed for educational environments, featuring role-based access control, subject-centric document retrieval, and interactive AI-driven quizzes.

## Key Features

- **Subject-Centric RAG Architecture**: Documents are bound to specific subjects. The conversational AI filters context dynamically based on the active subject, preventing cross-contamination of knowledge between unrelated domains.
- **Interactive Quiz Engine**: A dynamic "Generate Quiz" feature that bypasses standard semantic retrieval to randomly sample subject facts, prompting the LLM to stream a 5-question multiple-choice quiz directly into the chat session, complete with a hidden answer key.
- **Relational Data & Persistent Vector Storage**: Uses SQLite for strict relational data mapping (Users, Roles, Subjects, Sources, Chat Histories) and integrates with ChromaDB for saving and querying vector embeddings with advanced metadata filtering (`subject_id`, `visibility`, etc.).
- **Multiple LLM Integration**: Powered by `ChatOllama` for 100% offline generation using local models (e.g., `gemma_ollama`, `mistral_ollama`), while also seamlessly supporting NVIDIA's cloud APIs (e.g., `minimax_nvidia`) via environment variables.
- **Local Embeddings & Reranking**: Uses `HuggingFaceEmbeddings` (`all-MiniLM-L6-v2`) for vectorization, supercharged by a **BGE GPU Reranker** (`BAAI/bge-reranker-base`) for precision context retrieval.
- **Advanced Document Processing**: Built-in PDF processing using `pdf2image` and LLM-driven Vision OCR to extract text from complex or scanned documents asynchronously.
- **Role-Based Access Control (RBAC)**: Secure FastAPI backend enforces strict authentication using `X-Auth-Token` headers. The system isolates Admin/Teacher routes for document ingestion while keeping Student/Public chat routes accessible.

## Tech Stack

### AI & Machine Learning
- **LangChain** (RAG Pipeline Orchestration)
- **ChromaDB** (Vector Store with Metadata Filtering)
- **Ollama / NVIDIA API** (LLM Execution)
- **HuggingFace** (Embeddings & Cross-Encoder Reranking)

### Backend
- **FastAPI** (Async Web API)
- **SQLAlchemy & SQLite** (Relational Database ORM)
- **Python 3.10+** (Core Logic)
- **Uvicorn** (ASGI Server)

### Frontend
- **React 18 + Vite** (Production Web App)
- **Framer Motion & Lucide React** (UI/UX)
- **React Markdown** (Streaming chat rendering & collapsible custom blocks)

## Architecture & File Structure

```text
RAG/
├── backend/                # FastAPI Backend Ecosystem
│   ├── main.py             # FastAPI entry point & API Routing
│   ├── authentication/     # Security, Tokens, and RBAC logic (auth.py, router.py)
│   ├── chat/               # LangChain RAG pipeline & chat routing (rag_backend.py, router.py)
│   ├── db/                 # SQLAlchemy ORM Models, Migrations & Init (models.py, database.py, seed.py)
│   ├── sources/            # Document ingestion and management routes
│   ├── subjects/           # Educational subjects routing
│   ├── chroma_db/          # Persistent Chroma vector store
│   └── .env                # Environment variables (API Keys, URLs)
├── frontend/               # Vite + React Frontend
│   ├── src/                # React components and pages
│   └── package.json        # Frontend dependencies
├── inputs/                 # Default directory for local document processing
└── README.md               # Project documentation
```

## Prerequisites

- **Ollama**: Installed and running locally. Pull the required models:
  ```bash
  ollama run gemma:2b # Or whatever your preferred local model is
  ```
- **NVIDIA API Key**: (Optional) For utilizing cloud models via LangChain NVIDIA integration.
- **System Packages**: Required for PDF OCR.
  ```bash
  # Ubuntu/Debian
  sudo apt install poppler-utils
  # macOS
  brew install poppler
  ```
- **Python**: Version 3.10 or higher.
- **Node.js**: Version 18 or higher (for the React frontend).

## Setup & Installation

### 1. Python Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt  # Ensure dependencies match current architecture
```

Set up your `.env` file in the `backend` directory:
```env
OLLAMA_BASE_URL=http://localhost:11434
NVIDIA_API_KEY=your_nvidia_api_key_here
```

### 2. Database Initialization
Before running the backend, initialize the SQLite database and create the default admin user:
```bash
cd backend
python db/seed.py
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

## How To Run

1. **Start the Backend:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload --port 8000
   ```
   *The API will be available at `http://localhost:8000`. API Docs available at `http://localhost:8000/docs`.*

2. **Start the Frontend:**
   Open a new terminal window.
   ```bash
   cd frontend
   npm run dev
   ```
   *The frontend will be available at `http://localhost:5173`.*

## Backend API Documentation (Overview)

The FastAPI server (`backend/main.py`) exposes several endpoints grouped by role context. Administrative endpoints require an `X-Auth-Token` header.

### Admin/Teacher Portal (Knowledge Base)
- `POST /api/admin/subjects`: Create a new educational subject.
- `POST /api/admin/sources`: Upload and ingest PDF/Text files into a specific subject. Ingestion runs asynchronously in the background.
- `DELETE /api/admin/sources/{source_id}`: Remove a source file and automatically purge its vectors from ChromaDB.

### Student Portal (Query & Chat)
- `GET /api/subjects`: List all available subjects for the UI dropdown.
- `GET /api/subjects/{subject_id}/sources`: List the documents backing a specific subject.
- `POST /api/chats`: Create a new chat session.
- `GET /api/chats/{chat_id}/history`: Load the chat history.
- `POST /api/chats/{chat_id}/query`: Submit a query to the RAG system. Accepts an `is_quiz` flag to trigger the custom Quiz Generator. Returns a Server-Sent Events (SSE) stream for real-time typing effect.
