from pydantic import BaseModel, Field
from typing import Literal

class UIElement(BaseModel):
    kind: Literal["input", "select", "checkbox", "button", "link", "list", "text"]
    label: str = Field(min_length=1)
    purpose: str


class AcceptanceCriterion(BaseModel):
    id: str = Field(pattern=r"^F\d+-AC\d+$")
    statement: str
    priority: Literal["P1", "P2", "P3", "P4"] = Field(
        description="P1 core, P2 main flows, P3 edge cases, P4 polish"
    )

class Coverage(BaseModel):
    requirement_id: str
    feature_ids: list[str] = Field(min_length=1)

class Feature(BaseModel):
    id: str = Field(pattern=r"^F\d+$")
    name: str
    requirement_ids: list[str] = Field(min_length=1)
    description: str
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=1)


class LogicFunction(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    file: str
    language: Literal["javascript", "python"]
    signature: str
    description: str
    error_conditions: list[str]


class EnvVar(BaseModel):
    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    used_by: Literal["frontend", "backend"]
    secret: bool
    purpose: str


class Column(BaseModel):
    name: str
    type: str
    nullable: bool
    notes: str = ""


class Table(BaseModel):
    name: str
    columns: list[Column]
    access_rules: list[str] = Field(min_length=1)


class ErrorResponse(BaseModel):
    status: int = Field(ge=400, le=599)
    meaning: str


class ApiRoute(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    purpose: str
    request_body: str
    response_body: str
    auth_required: bool
    error_responses: list[ErrorResponse] = Field(min_length=1)


class Risk(BaseModel):
    risk: str
    mitigation: str


class PlannedFile(BaseModel):
    path: str
    owner: Literal["frontend", "backend", "database"]
    purpose: str