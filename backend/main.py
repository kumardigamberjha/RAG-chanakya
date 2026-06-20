from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from db.database import init_db
from authentication.router import router as auth_router
from chat.router import router as chat_router
from subjects.router import router as subjects_router
from sources.router import router as sources_router

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

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(subjects_router)
app.include_router(sources_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)