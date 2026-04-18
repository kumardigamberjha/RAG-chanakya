import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma


DATA_PATH = "/media/digamber-jha/D6/Models/LocalLM/RAG/inputs/"
DB_PATH = "/media/digamber-jha/D6/Models/LocalLM/RAG/db/"

def build_vector_db():
    # Dummy data
    os.makedirs(DB_PATH, exist_ok=True)
    test_file_path = os.path.join(DATA_PATH, "coding_india_script.txt")
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write("Coding India is a platform for tech tutorials. Digamber Jha is the founder. "
                    "We focus on Python, Django, React, and AI Agents. Sanjaya is our offline RAG project. "
                    "It uses local models for maximum privacy. Vectors are mathematical representations of text.")

    print(f"[SYSTEM] Created test document at {test_file_path}")


    # 2. Data Load Karna
    file_path = os.path.join(DATA_PATH, "coding_india_script.txt")
    loader = TextLoader(file_path)
    print("LOader: ", loader)
    document = loader.load()
    print("Document: ", document)
    print("[SYSTEM] Document loaded.")

    # 3. Chunks Banana (The core logic)
    # Hum RecursiveCharacterTextSplitter use kar rahe hain, jo words/sentences ko properly todta hai
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=100,
        chunk_overlap=20,
        length_function=len
    )
    print("Text Splitter: ", text_splitter)
    chunks = text_splitter.split_documents(document)
    print(f"[SYSTEM] Document split into {len(chunks)} chunks.")
    print("Chunks: ", chunks)

    # Chunk display karke dekhna
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(chunk.page_content)

    # 4. Embeddings Model Initialize Karna (Offline Model)
    print("\n[SYSTEM] Downloading/Loading Local Embedding Model (This may take a minute on first run)...")
    embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    print("Embedding Model: ", embedding_model)

    # 5. ChromaDB mein store karna
    print("[SYSTEM] Saving to ChromaDB...")
    db = Chroma.from_documents(
        documents=chunks, 
        embedding=embedding_model, 
        persist_directory=DB_PATH
    )
    print(f"[SYSTEM] Mission Complete. Vectors securely stored at {DB_PATH}")

if __name__ == "__main__":
    build_vector_db()