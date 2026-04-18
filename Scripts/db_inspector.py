import chromadb

def inspect_database():
    print("[SYSTEM] Bypassing LangChain. Connecting directly to Bare-Metal ChromaDB...\n")

    # 1. Database folder se direct connection
    client = chromadb.PersistentClient(path="../db")

    # 2. Collection nikalna (LangChain default collection ka naam "langchain" rakhta hai)
    try:
        collection = client.get_collection(name="langchain")
        print(f"[SYSTEM] Connection Successful. Total Chunks in DB: {collection.count()}\n")
    except Exception as e:
        print("[ERROR] Collection not found. Have you ingested data yet?")
        return

    # ==========================================
    # MISSION 1: PEEK INSIDE THE DATA STRUCTURE
    # ==========================================
    print("--- [DATA STRUCTURE EXPOSE] ---")
    
    # Hum sirf pehla 1 chunk nikal rahe hain pura structure dekhne ke liye
    # include=["embeddings"] add karne se tum vectors bhi dekh sakte ho
    data = collection.get(
        limit=1, 
        include=["metadatas", "documents", "embeddings"]
    )
    
    print(f"ID: {data['ids'][0]}")
    print(f"Metadata: {data['metadatas'][0]}")
    print(f"Document Text: {data['documents'][0][:100]}... (truncated)")
    
    # Embedding structure print karna (First 5 numbers out of 384)
    vector = data['embeddings'][0]
    print(f"Embedding Vector (Total Dimensions: {len(vector)}): {vector[:5]}... \n")

    # ==========================================
    # MISSION 2: MANUAL QUERY (NO LANGCHAIN)
    # ==========================================
    print("--- [MANUAL SEARCH EXECUTION] ---")
    
    # Bina kisi LLM ya wrapper ke, purely math aur Chroma API ka use karke search
    results = collection.query(
        query_texts=["What is the focus of Coding India?"],
        n_results=2, # Top 2 closest matches
        include=["documents", "distances"] # Distances = Kitna close match hai
    )

    print(f"Manual Query: 'What is the focus of Coding India?'")
    for i in range(len(results['documents'][0])):
        text = results['documents'][0][i]
        distance = results['distances'][0][i] # Kam distance = Better match
        print(f"\nMatch {i+1} (Distance: {distance:.4f}):")
        print(f"{text}")

if __name__ == "__main__":
    inspect_database()