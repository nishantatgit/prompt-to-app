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
from api.voice import router as voice_router  # noqa: E402
from api.credits import router as credits_router  # noqa: E402
from api.feedback import router as feedback_router  # noqa: E402
from api.push import router as push_router  # noqa: E402

DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def cors_origins(raw: str | None) -> list[str]:
    """The sites allowed to call the API, from CORS_ORIGINS (comma separated).

    A browser sends its origin as scheme and host only, so an entry written
    "https://vyskar.com/" or with a space after a comma ("a, b") would never
    match and that site's every request would fail with a CORS error. Spaces
    and a trailing slash are dropped, blank entries skipped, and an empty
    setting falls back to the local dev server.
    """
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",")]
    return [o for o in origins if o] or [DEFAULT_CORS_ORIGINS]


app = FastAPI()
app.include_router(router)
app.include_router(voice_router)
app.include_router(credits_router)
app.include_router(feedback_router)
app.include_router(push_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(os.environ.get("CORS_ORIGINS")),
    allow_methods=["GET", "POST"],
    # Authorization: the admin page at app.vyskar.com/admin sends ADMIN_TOKEN.
    allow_headers=["Content-Type", "X-Vyskar-Visitor", "Authorization"],
)
