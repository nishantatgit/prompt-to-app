from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class BuildRequest(BaseModel):
    prompt: str

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/build")
def build(req: BuildRequest):
    # Stub for now; the agent comes later
    return {"status": "received", "prompt": req.prompt}