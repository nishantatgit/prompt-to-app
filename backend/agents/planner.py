from pathlib import Path, PurePosixPath
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, model_validator

PLANNER_PROMPT = (Path(__file__).parent / "prompts" / "planner.md").read_text()

PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=PLANNER_PROMPT),
        ("human", "<user_request>{prompt}</user_request>"),
    ]
)


class Feature(BaseModel):
    name: str
    description: str
    acceptance_criteria: list[str]


class Column(BaseModel):
    name: str
    type: str
    nullable: bool
    notes: str = ""


class Table(BaseModel):
    name: str
    columns: list[Column]
    access_rules: list[str]


class ApiRoute(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    purpose: str
    request_body: str
    response_body: str
    auth_required: bool


class PlannedFile(BaseModel):
    path: str
    owner: Literal["frontend", "backend", "database"]
    purpose: str


PREFIX_OWNERS = {
    "api/": "backend",
    "supabase/migrations/": "database",
    "src/": "frontend",
}

from pathlib import PurePosixPath

ALLOWED_EXTENSIONS = {
    "frontend": {".js", ".jsx", ".css", ".html", ".json", ".svg"},
    "backend": {".py", ".txt"},
    "database": {".sql"},
}

# Root level files and the owner each must have
ROOT_FILES = {
    "index.html": "frontend",
    "package.json": "frontend",
    "vite.config.js": "frontend",
    "vercel.json": "frontend",
    "requirements.txt": "backend",
}


class Plan(BaseModel):
    summary: str
    assumptions: list[str]
    features: list[Feature]
    needs_backend: bool
    needs_database: bool
    needs_auth: bool
    tables: list[Table]
    api_routes: list[ApiRoute]
    files: list[PlannedFile]

    @model_validator(mode="after")
    def check_consistency(self):
        if not self.needs_backend and self.api_routes:
            raise ValueError("api_routes given but needs_backend is false")
        if not self.needs_database and self.tables:
            raise ValueError("tables given but needs_database is false")
        if self.needs_auth and not self.needs_database:
            raise ValueError("needs_auth requires needs_database")

        paths = [f.path for f in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate file paths in plan")

        for f in self.files:
            if f.path.startswith("/") or ".." in f.path:
                raise ValueError(f"unsafe file path: {f.path}")
            for prefix, required_owner in PREFIX_OWNERS.items():
                if f.path.startswith(prefix) and f.owner != required_owner:
                    raise ValueError(
                        f"{f.path} is under {prefix} so its owner must be {required_owner}"
                    )
            if f.owner == "backend" and not self.needs_backend:
                raise ValueError(f"backend file {f.path} but needs_backend is false")

            extension = PurePosixPath(f.path).suffix
            if extension not in ALLOWED_EXTENSIONS[f.owner]:
                raise ValueError(
                    f"{f.path} has extension '{extension}', "
                    f"which is not allowed for {f.owner} files"
                )

            if "/" not in f.path:
                expected_owner = ROOT_FILES.get(f.path)
                if expected_owner is None:
                    raise ValueError(f"unexpected file in project root: {f.path}")
                if f.owner != expected_owner:
                    raise ValueError(f"{f.path} must have owner {expected_owner}")

        return self


def make_planner(llm: BaseChatModel):
    chain = PROMPT | llm.with_structured_output(Plan, include_raw=True)

    def planner(state: dict) -> dict:
        out = chain.invoke({"prompt": state["prompt"]})

        if out["parsing_error"] is not None:
            return {
                "plan": None,
                "errors": [f"Planning failed: {out['parsing_error']}"],
            }

        plan: Plan = out["parsed"]
        return {"plan": plan.model_dump(), "errors": []}

    return planner
