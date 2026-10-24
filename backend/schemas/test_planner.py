from typing import Annotated, Literal, Union
from pydantic import BaseModel, field_validator, model_validator, Field
import json

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
    size: Literal["small", "medium", "large", "extra_large"]


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


class E2ETest(BaseModel):
    id: str = Field(pattern=r"^E\d+$")
    criterion_id: str
    description: str
    code: str = Field(description="The complete Playwright spec file content.")

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