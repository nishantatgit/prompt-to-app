import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator, model_validator

from agents.architect import Architecture

TEST_PLANNER_PROMPT = (Path(__file__).parent / "prompts" / "test_planner.md").read_text()

PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=TEST_PLANNER_PROMPT),
        (
            "human",
            "<user_request>{prompt}</user_request>\n\n"
            "<architecture>{architecture}</architecture>\n\n"
            "{feedback}",
        ),
    ]
)

User = Literal["anonymous", "user_a", "user_b", "admin"]


class UnitCase(BaseModel):
    id: str
    function: str
    description: str
    args: str = Field(description="JSON array of arguments, for example [1000, 10, 4]")
    expect: str = Field(default="", description="JSON value of the expected result")
    expect_error: bool = False

    @field_validator("args")
    @classmethod
    def args_is_json_array(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"args is not valid JSON: {e}") from e
        if not isinstance(parsed, list):
            raise ValueError("args must be a JSON array")
        return value

    @model_validator(mode="after")
    def expect_or_error(self):
        if self.expect_error and self.expect:
            raise ValueError(f"unit case {self.id}: use either expect or expect_error, not both")
        if not self.expect_error:
            if not self.expect:
                raise ValueError(f"unit case {self.id}: expect is required unless expect_error")
            try:
                json.loads(self.expect)
            except json.JSONDecodeError as e:
                raise ValueError(f"unit case {self.id}: expect is not valid JSON: {e}") from e
        return self


class ApiCase(BaseModel):
    id: str
    description: str
    as_user: User
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    body: str = Field(default="", description="JSON request body, empty for none")
    expect_status: int = Field(ge=100, le=599)
    expect_body_contains: str = Field(
        default="", description="JSON object whose fields must appear in the response"
    )

    @model_validator(mode="after")
    def json_fields(self):
        if self.body:
            try:
                json.loads(self.body)
            except json.JSONDecodeError as e:
                raise ValueError(f"api case {self.id}: body is not valid JSON: {e}") from e
        if self.expect_body_contains:
            try:
                parsed = json.loads(self.expect_body_contains)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"api case {self.id}: expect_body_contains is not valid JSON: {e}"
                ) from e
            if not isinstance(parsed, dict):
                raise ValueError(f"api case {self.id}: expect_body_contains must be a JSON object")
        return self


class DataAccessCase(BaseModel):
    id: str
    description: str
    table: str
    as_user: User
    operation: Literal["select", "insert", "update", "delete"]
    expect: Literal["allowed", "denied"]


class Goto(BaseModel):
    action: Literal["goto"]
    path: str


class Fill(BaseModel):
    action: Literal["fill"]
    label: str
    value: str


class Click(BaseModel):
    action: Literal["click"]
    label: str


class SelectOption(BaseModel):
    action: Literal["select"]
    label: str
    option: str


class Check(BaseModel):
    action: Literal["check"]
    label: str


class Press(BaseModel):
    action: Literal["press"]
    label: str
    key: Literal["Enter", "Escape", "Tab"]


class Reload(BaseModel):
    action: Literal["reload"]


class SetViewport(BaseModel):
    action: Literal["set_viewport"]
    width: int = Field(ge=320, le=1920)
    height: int = Field(ge=480, le=1080)


class LoginAs(BaseModel):
    action: Literal["login_as"]
    user: Literal["user_a", "user_b", "admin"]


class ExpectText(BaseModel):
    action: Literal["expect_text"]
    text: str = Field(min_length=1)


class ExpectNoText(BaseModel):
    action: Literal["expect_no_text"]
    text: str = Field(min_length=1)


class ExpectVisible(BaseModel):
    action: Literal["expect_visible"]
    label: str


class ExpectDisabled(BaseModel):
    action: Literal["expect_disabled"]
    label: str


class ExpectValue(BaseModel):
    action: Literal["expect_value"]
    label: str
    value: str


class ExpectCount(BaseModel):
    action: Literal["expect_count"]
    label: str
    count: int = Field(ge=0)


Step = Annotated[
    Union[
        Goto,
        Fill,
        Click,
        SelectOption,
        Check,
        Press,
        Reload,
        SetViewport,
        LoginAs,
        ExpectText,
        ExpectNoText,
        ExpectVisible,
        ExpectDisabled,
        ExpectValue,
        ExpectCount,
    ],
    Field(discriminator="action"),
]

ASSERTIONS = (ExpectText, ExpectNoText, ExpectVisible, ExpectDisabled, ExpectValue, ExpectCount)

TARGET_KINDS = {
    "fill": {"input"},
    "select": {"select"},
    "check": {"checkbox"},
    "click": {"button", "link", "checkbox"},
    "press": {"input"},
    "expect_visible": {"input", "select", "checkbox", "button", "link", "list", "text"},
    "expect_disabled": {"input", "select", "checkbox", "button"},
    "expect_value": {"input", "select"},
    "expect_count": {"list"},
}


class E2ETest(BaseModel):
    id: str
    criterion_id: str
    description: str
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def has_assertion(self):
        if not any(isinstance(s, ASSERTIONS) for s in self.steps):
            raise ValueError(f"e2e test {self.id} has no expect step")
        return self


class TestPlan(BaseModel):
    strategy: str = Field(description="Short summary of what each test layer covers and why")
    unit_cases: list[UnitCase]
    api_cases: list[ApiCase]
    data_access_cases: list[DataAccessCase]
    e2e_tests: list[E2ETest] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = (
            [c.id for c in self.unit_cases]
            + [c.id for c in self.api_cases]
            + [c.id for c in self.data_access_cases]
            + [t.id for t in self.e2e_tests]
        )
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"test ids must be unique, duplicated: {sorted(duplicates)}")
        return self


def check_against(plan: TestPlan, arch: Architecture) -> list[str]:
    """Return every problem found. An empty list means the test plan is accepted."""
    errors: list[str] = []
    login_users = {"user_a", "user_b", "admin"}

    # Unit tests
    functions = {fn.name: fn for fn in arch.functions}
    unit_by_function = defaultdict(list)
    for case in plan.unit_cases:
        if case.function not in functions:
            errors.append(f"unit case {case.id}: function '{case.function}' is not in architecture")
            continue
        unit_by_function[case.function].append(case)

    for name, fn in functions.items():
        cases = unit_by_function[name]
        if len(cases) < 2:
            errors.append(f"function {name}: needs at least 2 unit cases, has {len(cases)}")
        if fn.error_conditions and not any(c.expect_error for c in cases):
            errors.append(
                f"function {name}: declares error conditions but no unit case uses expect_error"
            )

    # API tests
    if plan.api_cases and not arch.needs_backend:
        errors.append("api_cases given but the architecture has no backend")

    patterns = arch.route_patterns()
    api_by_route = defaultdict(list)
    for case in plan.api_cases:
        route = next(
            (r for r, rx in patterns if r.method == case.method and rx.match(case.path)), None
        )
        if route is None:
            errors.append(f"api case {case.id}: {case.method} {case.path} matches no api route")
            continue
        if case.as_user in login_users and not arch.needs_auth:
            errors.append(f"api case {case.id}: as_user {case.as_user} but needs_auth is false")
        api_by_route[(route.method, route.path)].append(case)

    for route in arch.api_routes:
        key = (route.method, route.path)
        name = f"{route.method} {route.path}"
        cases = api_by_route[key]
        statuses = {c.expect_status for c in cases}
        if not any(200 <= s < 300 for s in statuses):
            errors.append(f"route {name}: needs at least one success (2xx) case")
        if not any(400 <= s < 500 for s in statuses):
            errors.append(f"route {name}: needs at least one client error (4xx) case")
        if route.auth_required and not any(
            c.as_user == "anonymous" and c.expect_status == 401 for c in cases
        ):
            errors.append(f"route {name}: requires auth, so needs an anonymous case expecting 401")
        for error in route.error_responses:
            if error.status not in statuses:
                errors.append(
                    f"route {name}: declared error {error.status} ({error.meaning}) is not tested"
                )

    # Data access tests
    if plan.data_access_cases and not arch.needs_database:
        errors.append("data_access_cases given but the architecture has no database")

    tables = {t.name for t in arch.tables}
    data_by_table = defaultdict(list)
    for case in plan.data_access_cases:
        if case.table not in tables:
            errors.append(
                f"data access case {case.id}: table '{case.table}' is not in architecture"
            )
            continue
        if case.as_user in login_users and not arch.needs_auth:
            errors.append(
                f"data access case {case.id}: as_user {case.as_user} but needs_auth is false"
            )
        data_by_table[case.table].append(case)

    for table in tables:
        outcomes = {c.expect for c in data_by_table[table]}
        if "allowed" not in outcomes:
            errors.append(f"table {table}: needs at least one 'allowed' data access case")
        if "denied" not in outcomes:
            errors.append(f"table {table}: needs at least one 'denied' data access case")

    # End to end tests
    elements = {e.label: e for e in arch.ui_elements}
    criterion_ids = arch.criterion_ids()
    covered_criteria = set()

    for test in plan.e2e_tests:
        if test.criterion_id not in criterion_ids:
            errors.append(f"e2e test {test.id}: criterion '{test.criterion_id}' does not exist")
        else:
            covered_criteria.add(test.criterion_id)

        for step in test.steps:
            where = f"e2e test {test.id}"
            if isinstance(step, Goto) and not step.path.startswith("/"):
                errors.append(f"{where}: goto path must start with '/'")
            if isinstance(step, LoginAs) and not arch.needs_auth:
                errors.append(f"{where}: login_as used but needs_auth is false")
            if isinstance(step, Reload) and arch.storage == "none":
                errors.append(f"{where}: reload used but storage is 'none', so nothing persists")

            allowed_kinds = TARGET_KINDS.get(step.action)
            if allowed_kinds:
                element = elements.get(step.label)
                if element is None:
                    errors.append(f"{where}: '{step.label}' is not declared in ui_elements")
                elif element.kind not in allowed_kinds:
                    errors.append(
                        f"{where}: {step.action} cannot target a {element.kind} ('{step.label}')"
                    )

    for missing in sorted(criterion_ids - covered_criteria):
        errors.append(f"criterion {missing}: has no e2e test")

    return errors


def make_test_planner(llm: BaseChatModel):
    chain = PROMPT | llm.with_structured_output(TestPlan, include_raw=True)

    def test_planner(state: dict) -> dict:
        attempts = state.get("test_planner_attempts", 0) + 1
        previous_error = state.get("test_planner_feedback", "")
        architecture = Architecture.model_validate(state["architecture"])

        feedback = ""
        if previous_error:
            feedback = (
                "Your previous test plan was rejected with these errors:\n"
                f"{previous_error}\n"
                "Return a corrected test plan that fixes all of them."
            )

        out = chain.invoke(
            {
                "prompt": state["prompt"],
                "architecture": architecture.model_dump_json(indent=2),
                "feedback": feedback,
            }
        )

        if out["parsing_error"] is not None:
            problems = [str(out["parsing_error"])]
        else:
            problems = check_against(out["parsed"], architecture)

        if problems:
            return {
                "test_plan": None,
                "test_planner_attempts": attempts,
                "test_planner_feedback": "\n".join(f"- {p}" for p in problems),
                "errors": [f"Test planning failed: {p}" for p in problems],
            }

        return {
            "test_plan": out["parsed"].model_dump(),
            "test_planner_attempts": attempts,
            "test_planner_feedback": "",
            "errors": [],
        }

    return test_planner
