# Project: Wings of AI B2B RAG & Sanjaya RAG

## Executive Summary
**Wings of AI B2B RAG** (codenamed Sanjaya RAG) is a highly robust, privacy-first, fully local Retrieval-Augmented Generation (RAG) ecosystem. It is designed to allow organizations, particularly educational institutes, to upload proprietary documents and enable context-aware conversational AI over that data. 

To guarantee absolute data privacy, the entire pipeline operates on-device without any external API calls, utilizing local embeddings (`HuggingFace`), local Large Language Models (`Ollama`), and a local vector database (`ChromaDB`).

---

## 📖 Case Study: B2B Educational Institute Rollout

### The Challenge
Educational institutes face a significant hurdle in adopting AI: they want to empower students to interact dynamically with course syllabi, textbooks, and notes, but **cannot risk sending sensitive curriculum data, proprietary materials, or student queries to external providers like OpenAI.** They need an AI system that is as smart as ChatGPT but completely air-gapped and capable of separating data between different classes or schools.

### The Solution: Multi-Tenant Local RAG
We architected a 100% offline, multi-tenant RAG pipeline leveraging FastAPI, React, and local open-weight models.

1. **Teacher Portal (Data Ingestion)**
   - Teachers upload complex PDFs (including scanned images).
   - The system leverages a **background multithreaded OCR pipeline** using `pdf2image` and a Vision LLM (`glm-5.2:cloud` with vision capabilities) to extract text seamlessly without blocking the main server thread.
   - The data is vectorized using `all-MiniLM-L6-v2` and stored in ChromaDB. 
   - **Crucial Security Feature:** Every ingestion request is tagged with an `X-Tenant-ID` (e.g., the School ID). ChromaDB collections are strictly partitioned by this ID.

2. **Student Portal (Query & Chat)**
   - A student logs in and asks a question (e.g., *"What were the key principles of Chanakya Neeti?"*).
   - The API receives the request alongside the `X-Tenant-ID`.
   - The LangChain engine checks the chat history and **reformulates** the question to be contextually complete.
   - Documents are retrieved from ChromaDB, but before generation, they are passed through a **BGE GPU Cross-Encoder Reranker** (`BAAI/bge-reranker-base`) to bubble up the most relevant folios.
   - Finally, `glm-5.2:cloud` generates the answer and **streams it back** to the frontend in real-time via Server-Sent Events (SSE), completely citing its sources.

### The Results
- **Zero Data Leakage:** All data remains on the school's local servers.
- **High Accuracy:** The GPU reranker ensures only the most highly correlated syllabus sections are passed to the LLM, effectively eliminating hallucinations.
- **Scalability:** The multi-tenant architecture allows a single backend deployment to securely serve dozens of isolated school environments.

---

## Folder Structure

```text
RAG/
├── app.py                  # Standalone Streamlit local UI prototype (Sanjaya RAG)
├── backend/                # FastAPI Backend Ecosystem
│   ├── main.py             # FastAPI entry point & API Routing
│   ├── authentication/     # Security, JWT tokens, and RBAC logic
│   ├── chat/               # LangChain RAG pipeline & chat routing
│   ├── db/                 # SQLAlchemy ORM Models, SQLite DB & Migrations
│   ├── sources/            # Document ingestion and management routes
│   ├── subjects/           # Educational subjects routing
│   ├── chroma_db/          # Persistent Chroma vector store
│   └── .env                # Environment variables
├── frontend/               # Vite + React Frontend Architecture
│   ├── src/                # React components and pages
│   ├── package.json        # Node dependencies
│   └── vite.config.js      # Vite configuration
├── inputs/                 # Default directory for legacy source documents
├── redesign.html           # UI redesign draft (v1)
├── redesign_v2.html        # UI redesign draft (v2)
└── README.md               # Quick-start project documentation
```

---

## File Structure (Core Components)

### Backend
- **`main.py`**: The core API server. Handles CORS, route definitions, async streaming responses, and includes modular routers.
- **`chat/rag_backend.py`**: The AI heart of the system. Configures the LangChain pipeline, document loaders, RecursiveCharacterTextSplitter, local HuggingFace embeddings, BGE Reranker, local Ollama LLM, and parallel PDF OCR ingestion.
- **`db/` Module**: Contains SQLAlchemy models, database initialization, and the persistent `chats.db` SQLite database. Replaces legacy JSON registries.
- **`authentication/` Module**: Handles JWT-based authentication and Role-Based Access Control (RBAC).

### Frontend
- **`src/`**: Contains the React application logic (App.jsx, components, API integration layer).
- **`package.json`**: Defines critical UI dependencies like `framer-motion` (for animations) and `lucide-react` (for iconography).
- **`app.py`**: A secondary, standalone Streamlit frontend featuring pixel-perfect custom CSS for immediate local testing and rapid prototyping without starting the Node server.

---

## Technologies Used

### Backend & AI Pipeline
- **FastAPI**: High-performance asynchronous web framework for the API.
- **LangChain**: Framework orchestrating the complex RAG chain (Retrievers, Prompts, LLMs).
- **ChromaDB**: Lightweight, persistent vector database for storing and retrieving document embeddings.
- **Ollama**: Local LLM execution environment (configured for `glm-5.2:cloud`).
- **HuggingFace Embeddings**: Uses the lightweight `all-MiniLM-L6-v2` for generating vectors.
- **BGE Cross-Encoder Reranker**: Uses `BAAI/bge-reranker-base` to dynamically re-score and compress retrieved documents for maximum relevance.
- **pdf2image & Pillow**: Used in tandem with LLMs for processing scanned PDF pages.

### Frontend
- **React**: UI library.
- **Vite**: Modern frontend build tool for instantaneous hot module replacement.
- **Streamlit**: Python-native UI library used for the secondary rapid-prototype client.
- **Framer Motion**: For smooth UI animations and transitions in the React app.

---

## API Documentation (B2B Multi-Tenant)

*Note: All API endpoints below require standard Bearer token authentication via JWT.*

### 1. Teacher Portal (Knowledge Base)
- `POST /api/admin/subjects`: Creates a new educational subject.
- `POST /api/admin/sources`: Uploads and ingests PDF/TXT files into a specific subject. Triggers a background asynchronous task for OCR and ingestion.
- `DELETE /api/admin/sources/{source_id}`: Physically deletes the file and purges its corresponding chunk vectors from ChromaDB.

### 2. Student Portal (Conversations)
- `GET /api/subjects`: Retrieves all subjects available.
- `POST /api/chats`: Initializes a new chat session.
- `GET /api/chats`: Retrieves all chat sessions.
- `DELETE /api/chats/{chat_id}`: Deletes a chat session and purges its history.
- `GET /api/chats/{chat_id}/history`: Retrieves the full human/AI conversation history for UI rendering.
- `POST /api/chats/{chat_id}/query`: Submits a user query. The backend processes the RAG chain and returns an asynchronous **Server-Sent Events (SSE)** stream of LLM tokens, concluding with a JSON payload of provenance/source citations.

---

## How to Run

### Method 1: The Standalone App (Sanjaya RAG UI)
For a quick local chat interface without needing the full client-server split.
```bash
streamlit run app.py
```

### Method 2: Production Client-Server Stack
For the full B2B application featuring multi-tenancy.

**1. Start the Backend:**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```
*API docs available at `http://localhost:8000/docs`.*

**2. Start the Frontend:**
```bash
cd frontend
npm install
npm run dev
```
*Web app available at `http://localhost:5173`.*
