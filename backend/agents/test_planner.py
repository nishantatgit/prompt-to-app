from collections import defaultdict
from pathlib import Path
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from agents.architect import Architecture
from schemas.test_planner import TestPlan

FORBIDDEN_LOCATORS = {
    "locator('..')": r"locator\(\s*['\"]\.\.['\"]\s*\)",
    "XPath": r"xpath=|locator\(\s*['\"]//",
    "CSS selectors": r"locator\(\s*['\"][.#\[a-zA-Z]",
    ".nth()": r"\.nth\(",
    ".first() or .last()": r"\.(first|last)\(\)",
    "toHaveCount on a list itself": r"getByRole\(\s*['\"]list['\"][^)]*\)\s*\)\.toHaveCount",
}

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


def forbidden_locators(code: str) -> list[str]:
    return [name for name, pattern in FORBIDDEN_LOCATORS.items() if re.search(pattern, code)]


def drop_invalid_tests(plan: TestPlan, arch: Architecture) -> tuple[TestPlan, list[str], list[str]]:
    """Remove invalid unit cases and e2e tests instead of rejecting the whole plan.

    Returns the cleaned plan, a note for every dropped test, and the
    acceptance criteria left without any e2e test.
    """
    dropped: list[str] = []

    # Unit cases: keep only cases for functions the architecture defines.
    functions = {fn.name for fn in arch.functions}
    unit_cases = []
    for case in plan.unit_cases:
        if case.function not in functions:
            dropped.append(f"unit case {case.id}: function '{case.function}' is not in architecture")
        else:
            unit_cases.append(case)

    # E2E tests: keep only tests for real criteria, with an assertion and allowed locators.
    criterion_ids = arch.criterion_ids()
    e2e_tests = []
    for test in plan.e2e_tests:
        if test.criterion_id not in criterion_ids:
            dropped.append(f"e2e test {test.id}: criterion '{test.criterion_id}' does not exist")
            continue
        if "expect(" not in test.code:
            dropped.append(f"e2e test {test.id}: has no expect assertion")
            continue
        found = forbidden_locators(test.code)
        if found:
            dropped.append(f"e2e test {test.id}: uses {', '.join(found)}")
            continue
        e2e_tests.append(test)

    covered = {test.criterion_id for test in e2e_tests}
    untested_criteria = sorted(criterion_ids - covered)

    cleaned = plan.model_copy(update={"unit_cases": unit_cases, "e2e_tests": e2e_tests})
    return cleaned, dropped, untested_criteria


def check_against(plan: TestPlan, arch: Architecture) -> list[str]:
    """Problems that dropping tests cannot fix. An empty list means the plan is accepted."""
    errors: list[str] = []
    login_users = {"user_a", "user_b", "admin"}

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
            plan, dropped, untested = drop_invalid_tests(out["parsed"], architecture)
            problems = check_against(plan, architecture)

        if problems:
            return {
                "test_plan": None,
                "test_planner_attempts": attempts,
                "test_planner_feedback": "\n".join(f"- {p}" for p in problems),
                "errors": [f"Test planning failed: {p}" for p in problems],
            }

        test_plan = plan.model_dump()
        # Recorded for the test report: what was removed and what is no longer covered.
        test_plan["dropped_tests"] = dropped
        test_plan["untested_criteria"] = untested

        return {
            "test_plan": test_plan,
            "test_planner_attempts": attempts,
            "test_planner_feedback": "",
            "errors": [],
        }

    return test_planner