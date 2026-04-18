# Chanakya Neeti Local RAG

This project is a deeply local, privacy-first Retrieval-Augmented Generation (RAG) system built to interact with "Chanakya Neeti" and other documents offline. It features a complete pipeline from ingesting PDF documents to creating a context-aware conversational AI, avoiding any external APIs to ensure your data stays fully on-device.

## Key Features

- **100% Offline Generation**: Powered by `ChatOllama` utilizing local models (like `mistral:latest`).
- **Local Embeddings**: Uses `HuggingFaceEmbeddings` with the lightweight and capable `all-MiniLM-L6-v2` Sentence Transformer model.
- **Persistent Vector Storage**: Integrates with `Chroma` for saving and querying vector embeddings offline without needing a standalone vector database server.
- **History-Aware Conversations**: Implements LangChain's memory and history-aware retrievers to provide context-driven follow-ups during chat sessions.
- **Bare-Metal Database Inspection**: Includes tools to bypass the LangChain wrapper, letting you directly query and inspect vectors and chroma collections.

## Architecture & Scripts

The project is broken into distinct scripts, each modularizing a critical piece of the RAG puzzle.

### 1. Vector Database Builder (`Scripts/ingest.py`)
This script focuses on processing raw text. It handles loading data, chunking using `RecursiveCharacterTextSplitter`, generation of embeddings, and ultimately persisting the `ChromaDB` into the `db/` folder. It serves as a testing ground for text ingestion.

### 2. Conversational RAG Engine (`Scripts/rag_script.py`)
The main script for running your Chanakya Neeti offline chat interface. 
- Automatically loads all PDFs from the `inputs/` directory.
- Chunks and embeds the document contents.
- Initiates the `ChatOllama` LLM and builds a sophisticated chain (`create_history_aware_retriever` + `create_stuff_documents_chain`) to answer queries interactively.
- Run it to enter a continuous command-line terminal chat session capable of remembering previous turns contextually.

### 3. Database Inspector (`Scripts/db_inspector.py`)
A utility script designed for debugging and transparency. It strips away the LangChain abstraction to connect directly with the `Chroma` persistent client. You can view the hidden structures—internal IDs, multi-dimensional embedding values, and manually query the DB through math and distance algorithms outside the LLM context.

## Prerequisites

- [Ollama](https://ollama.com/) installed and running locally with the `mistral` model pulled (`ollama run mistral`).
- Python 3.10+
- The `inputs/` directory setup with the Chanakya Neeti PDF (e.g., `chaaNakyaNiti.pdf`) or any text you wish to engage with.
- Required python packages (Install via `pip`):
  - `langchain`
  - `langchain-community`
  - `langchain-huggingface`
  - `langchain-ollama`
  - `sentence-transformers`
  - `chromadb`
  - `pypdf`

## How To Run

1. **Place your source material:** Ensure your Pdfs (like `chaaNakyaNiti.pdf`) are inside the `inputs/` directory.
2. **Launch the conversational Interface:** Navigate into the `Scripts` directory and run:

```bash
python rag_script.py
```
Type your questions to interact with Chanakya Neeti. Type `exit` or `quit` to end the session.

3. **Inspect the Vectors (Optional):** Run `python db_inspector.py` to get a glance underneath the hood at how ChromaDB stored the embeddings.
