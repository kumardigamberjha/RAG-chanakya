import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.documents import Document
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

class DummyRetriever:
    def invoke(self, query):
        return [Document(page_content="dummy context")]
    async def ainvoke(self, query):
        return [Document(page_content="dummy context")]

async def main():
    llm = ChatOllama(model="gemma4:31b-cloud", base_url="http://localhost:11434")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the question based on context: {context}"),
        ("human", "{input}"),
    ])
    chain = create_stuff_documents_chain(llm, prompt)
    retriever = DummyRetriever()
    rag = create_retrieval_chain(retriever, chain)
    
    async for chunk in rag.astream({"input": "Hello!"}):
        print("CHUNK:", chunk)

asyncio.run(main())
