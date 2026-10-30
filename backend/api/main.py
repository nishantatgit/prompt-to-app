import os

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from config import ENV_FILE

loaded = load_dotenv(ENV_FILE)
print(
    f"[startup] .env loaded from {ENV_FILE}: {loaded} | "
    f"LANGSMITH_TRACING={os.getenv('LANGSMITH_TRACING')} | "
    f"LANGSMITH_PROJECT={os.getenv('LANGSMITH_PROJECT')}"
)

from fastapi import FastAPI  # noqa: E402

from api.routes import router  # noqa: E402

app = FastAPI()
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
