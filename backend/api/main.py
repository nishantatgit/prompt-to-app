import os

from dotenv import load_dotenv

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
