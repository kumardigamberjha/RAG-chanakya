from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, PyPDFDirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_classic.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage


def build_core_rag():
    print("[SYSTEM] Initiating Core RAG Pipeline...\n")

    # [PHASE 1: INGESTION]
    # Data load karna aur chunks mein todna
    # loader = PyPDFLoader("../inputs/chaaNakyaNiti.pdf")

    directory_path = "../inputs/"
    loader = PyPDFDirectoryLoader(directory_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    print(f"[SYSTEM] Data split into {len(chunks)} chunks.")

    print("\n[METADATA CHECK]:", chunks[0].metadata)

    # [PHASE 2: EMBEDDING]
    # Offline embedding model load karna aur DB mein dalna
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma.from_documents(chunks, embeddings)
    print("[SYSTEM] Vectors stored in temporary memory.")

    # [PHASE 3 & 4 PREP: LLM & PROMPT TEMPLATE]
    # Local LLM (Ollama) connect karna
    llm = ChatOllama(model="mistral:latest")
    
    prompt = ChatPromptTemplate.from_template("""
    System Directive: Answer the user's question based strictly on the provided context below. 
    If the answer is not in the context, say "Data missing from Knowledge Base."

    <context>
    {context}
    </context>

    Question: {input}
    """)# Prompt template design karna (Context injection)

    # [PHASE 4: THE CHAIN (Bringing it all together)]
    # Document combine karne ki chain
    doc_chain = create_stuff_documents_chain(llm, prompt)

    # Vector DB ko ek 'Retriever' banana jo top 2 closest chunks nikalega
    retriever = vector_db.as_retriever(search_kwargs={"k": 2})

    # Final RAG Chain: Retriever + LLM Chain
    # rag_chain = create_retrieval_chain(retriever, doc_chain)

    # [EXECUTION]
    # user_query = "what chankaya giving lession on daily life happiness?"
    # print(f"\n[USER QUERY]: {user_query}")

    # Chain ko invoke (run) karna
    # response = rag_chain.invoke({"input": user_query})

    # print("\n[AI RESPONSE]:")
    # print(response["answer"])

    # for i, doc in enumerate(response["context"]):
    #     # Metadata dictionary se 'source' aur 'page' nikalna
    #     source_file = doc.metadata.get("source", "Unknown Source")
    #     page_num = doc.metadata.get("page", "Unknown Page")
        
    #     print(f"Source {i+1} -> File: {source_file} | Page: {page_num}")
    # print("--------------------------------------------------")

    # ==========================================
    # MEMORY PHASE 1: THE REFORMULATOR
    # ==========================================
    # Yeh prompt LLM ko batata hai ki pichli chat padh kar naya question banao
    contextualize_q_system_prompt = """Given a chat history and the latest user question 
    which might reference context in the chat history, formulate a standalone question 
    which can be understood without the chat history. Do NOT answer the question, 
    just reformulate it if needed and otherwise return it as is."""

    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"), # Yahan purani chat aayegi
        ("human", "{input}"),
    ])

    # History-aware retriever chain banana
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    # ==========================================
    # MEMORY PHASE 2: THE ANSWER GENERATOR
    # ==========================================
    # Yeh final prompt hai jo LLM ko context aur history dekar answer mangega
    qa_system_prompt = """You are an assistant for question-answering tasks. 
    Use the following pieces of retrieved context to answer the question. 
    If you don't know the answer, just say that you don't know.
    
    Context: {context}"""

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"), # LLM ko yaad rakhne ke liye history
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    # Final Chain jo sab kuch jodti hai
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    # ==========================================
    # THE CHAT LOOP (Maintaining State)
    # ==========================================
    # Yeh array humari memory ko RAM mein store karega jab tak script chal rahi hai
    chat_history = []
    
    print("\n[SYSTEM] Sanjaya-RAG is Online. Type 'exit' to disconnect.")
    
    while True: # Yeh loop zaruri hai continuous chat ke liye
        user_query = input("\n[PLAYER]: ")
        if user_query.lower() in ['exit', 'quit']:
            print("[SYSTEM] Disconnecting...")
            break
            
        # Chain ko call karte waqt input ke sath chat_history bhi bhejni hai
        response = rag_chain.invoke({
            "input": user_query,
            "chat_history": chat_history
        })
        
        answer = response["answer"]
        print(f"\n[SANJAYA-RAG]: {answer}")
        
        # [CRITICAL STEP] Naye sawal aur jawab ko memory array mein save karna
        chat_history.extend([
            HumanMessage(content=user_query),
            AIMessage(content=answer)
        ])

if __name__ == "__main__":
    build_core_rag()