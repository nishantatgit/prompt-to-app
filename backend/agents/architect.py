import re
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, model_validator
from schemas.architect import ApiRoute, Coverage, EnvVar, Feature, LogicFunction, PlannedFile, Risk, Table, UIElement

ARCHITECT_PROMPT = (Path(__file__).parent / "prompts" / "architect.md").read_text()

PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=ARCHITECT_PROMPT),
    (
        "human",
        "<user_request>{prompt}</user_request>\n\n"
        "<requirements>{requirements}</requirements>\n\n"
        "{feedback}",
    ),
])


PREFIX_OWNERS = {
    "api/": "backend",
    "supabase/migrations/": "database",
    "src/": "frontend",
}

ALLOWED_EXTENSIONS = {
    "frontend": {".js", ".jsx", ".css", ".html", ".json", ".svg"},
    "backend": {".py", ".txt"},
    "database": {".sql"},
}

ROOT_FILES = {
    "index.html": "frontend",
    "package.json": "frontend",
    "vite.config.js": "frontend",
    "vercel.json": "frontend",
    "requirements.txt": "backend",
}

LANGUAGE_EXTENSIONS = {
    "javascript": {".js", ".jsx"},
    "python": {".py"},
}

SUPABASE_FRONTEND_VARS = {"VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"}


class Architecture(BaseModel):
    summary: str
    assumptions: list[str]
    coverage: list[Coverage] = Field(
        description="One entry for every requirement, in order, naming the "
                    "features that fulfil it. Write this before the features."
    )
    storage: Literal["none", "local_storage", "supabase"]
    needs_backend: bool
    needs_database: bool
    needs_auth: bool
    env_vars: list[EnvVar]
    ui_elements: list[UIElement]
    features: list[Feature] = Field(min_length=1)
    functions: list[LogicFunction]
    tables: list[Table]
    api_routes: list[ApiRoute]
    risks: list[Risk]
    files: list[PlannedFile] = Field(min_length=1)

    @model_validator(mode="after")
    def check_architecture(self):
        if not self.needs_backend and self.api_routes:
            raise ValueError("api_routes given but needs_backend is false")
        if self.needs_backend and not self.api_routes:
            raise ValueError("needs_backend is true but no api_routes are defined")
        if not self.needs_database and self.tables:
            raise ValueError("tables given but needs_database is false")
        if self.needs_auth and not self.needs_database:
            raise ValueError("needs_auth requires needs_database")
        if (self.storage == "supabase") != self.needs_database:
            raise ValueError("storage 'supabase' and needs_database must agree")
        return self

    @model_validator(mode="after")
    def check_ids_and_labels(self):
        feature_ids = [f.id for f in self.features]
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("feature ids must be unique")
        for f in self.features:
            for c in f.acceptance_criteria:
                if not c.id.startswith(f"{f.id}-"):
                    raise ValueError(f"criterion {c.id} must start with its feature id {f.id}")
        criterion_ids = [c.id for f in self.features for c in f.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("acceptance criterion ids must be unique")

        labels = [e.label for e in self.ui_elements]
        if len(labels) != len(set(labels)):
            raise ValueError("ui_elements labels must be unique")
        return self

    @model_validator(mode="after")
    def check_env_vars(self):
        names = [v.name for v in self.env_vars]
        if len(names) != len(set(names)):
            raise ValueError("env var names must be unique")
        for v in self.env_vars:
            if v.used_by == "frontend" and not v.name.startswith("VITE_"):
                raise ValueError(f"frontend env var {v.name} must start with VITE_")
            if v.secret and v.name.startswith("VITE_"):
                raise ValueError(
                    f"{v.name} is secret but starts with VITE_, which exposes it in the browser"
                )
            if v.secret and v.used_by == "frontend":
                raise ValueError(f"{v.name} is secret, so only the backend may use it")
        if self.needs_database and not SUPABASE_FRONTEND_VARS <= set(names):
            raise ValueError(
                "needs_database requires env vars VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY"
            )
        return self

    @model_validator(mode="after")
    def check_tables(self):
        names = [t.name for t in self.tables]
        if len(names) != len(set(names)):
            raise ValueError("table names must be unique")
        for t in self.tables:
            columns = {c.name for c in t.columns}
            for required in ("id", "created_at"):
                if required not in columns:
                    raise ValueError(f"table {t.name} is missing the {required} column")
        return self

    @model_validator(mode="after")
    def check_routes(self):
        keys = [(r.method, r.path) for r in self.api_routes]
        if len(keys) != len(set(keys)):
            raise ValueError("api routes must be unique by method and path")
        for r in self.api_routes:
            if not r.path.startswith("/api/"):
                raise ValueError(f"route {r.method} {r.path} must start with /api/")
            if r.auth_required and not self.needs_auth:
                raise ValueError(f"route {r.method} {r.path} requires auth but needs_auth is false")
            if r.auth_required and 401 not in {e.status for e in r.error_responses}:
                raise ValueError(f"route {r.method} {r.path} requires auth, so it must list a 401")
        return self

    @model_validator(mode="after")
    def check_files(self):
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
            if f.owner == "database" and not self.needs_database:
                raise ValueError(f"database file {f.path} but needs_database is false")
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

        if self.needs_backend:
            for required in ("api/index.py", "requirements.txt"):
                if required not in paths:
                    raise ValueError(f"needs_backend requires {required} in files")
        if self.needs_database:
            if "src/lib/supabase.js" not in paths:
                raise ValueError("needs_database requires src/lib/supabase.js in files")
            if not any(p.startswith("supabase/migrations/") for p in paths):
                raise ValueError("needs_database requires at least one migration file")
        return self

    @model_validator(mode="after")
    def check_functions(self):
        names = [fn.name for fn in self.functions]
        if len(names) != len(set(names)):
            raise ValueError("function names must be unique")
        paths = {f.path for f in self.files}
        for fn in self.functions:
            if fn.file not in paths:
                raise ValueError(f"function {fn.name} is in {fn.file}, which is not in files")
            extension = PurePosixPath(fn.file).suffix
            if extension not in LANGUAGE_EXTENSIONS[fn.language]:
                raise ValueError(
                    f"function {fn.name} is {fn.language} but {fn.file} has extension '{extension}'"
                )
            if fn.language == "python" and not self.needs_backend:
                raise ValueError(f"python function {fn.name} but needs_backend is false")
        return self

    # Helpers used by the test planner's cross checks

    def criterion_ids(self) -> set[str]:
        return {c.id for f in self.features for c in f.acceptance_criteria}

    def route_patterns(self) -> list[tuple[ApiRoute, re.Pattern]]:
        patterns = []
        for r in self.api_routes:
            # "/api/notes/{id}" matches "/api/notes/123"
            parts = re.split(r"\{[^/}]+\}", r.path)
            regex = "[^/]+".join(re.escape(p) for p in parts)
            patterns.append((r, re.compile(f"^{regex}$")))
        return patterns


def validate_features_requirements_mapping(
    architecture: dict, requirement_ids: set[str]
) -> list[str]:
    errors = []
    covered = set()

    for feature in architecture["features"]:
        if not feature["requirement_ids"]:
            errors.append(f"feature {feature['id']} lists no requirement_ids")
        for requirement_id in feature["requirement_ids"]:
            if requirement_id not in requirement_ids:
                errors.append(
                    f"feature {feature['id']} refers to unknown requirement {requirement_id}"
                )
            covered.add(requirement_id)

    for requirement_id in sorted(requirement_ids - covered):
        errors.append(f"requirement {requirement_id} is not fulfilled by any feature")

    return errors

def validate_coverage_matches_features(architecture: dict) -> list[str]:
    errors = []
    by_feature = {f["id"]: set(f["requirement_ids"]) for f in architecture["features"]}
    for entry in architecture["coverage"]:
        for feature_id in entry["feature_ids"]:
            if entry["requirement_id"] not in by_feature.get(feature_id, set()):
                errors.append(
                    f"coverage says {feature_id} fulfils {entry['requirement_id']}, "
                    f"but {feature_id}'s requirement_ids does not include it"
                )
    return errors

def make_architect(llm: BaseChatModel):
    chain = PROMPT | llm.with_structured_output(Architecture, include_raw=True)

    def architect(state: dict) -> dict:
        attempts = state.get("architect_attempts", 0) + 1
        previous_error = state.get("architect_feedback", "")

        feedback = ""
        if previous_error:
            feedback = (
                "Your previous architecture was rejected with this error:\n"
                f"{previous_error}\n"
                "Return a corrected architecture that fixes it."
            )

        requirements = state["requirements"]
        out = chain.invoke(
            {
                "prompt": state["prompt"],
                "requirements": json.dumps(requirements, indent=2),
                "feedback": feedback,
            }
        )

        if out["parsing_error"] is not None:
            problems = [str(out["parsing_error"])]
        else:
            architecture = out["parsed"].model_dump()
            requirement_ids = {r["id"] for r in requirements["requirements"]}
            problems = (
                validate_features_requirements_mapping(architecture, requirement_ids)
                + validate_coverage_matches_features(architecture)
            )

        if problems:
            return {
                "architecture": None,
                "architect_attempts": attempts,
                "architect_feedback": "\n".join(f"- {p}" for p in problems),
                "errors": [f"Architecture failed: {p}" for p in problems],
            }

        return {
            "architecture": out["parsed"].model_dump(),
            "architect_attempts": attempts,
            "architect_feedback": "",
            "errors": [],
        }

    return architect
