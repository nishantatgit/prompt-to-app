"""backend/.env.example is what a new setup copies to .env, so it must start
the API and name every setting the backend reads."""

import re
from pathlib import Path

from config import Settings

BACKEND = Path(__file__).resolve().parent.parent
EXAMPLE = BACKEND / ".env.example"
SOURCE_DIRS = ("api", "agents", "tools")
# Read only by the tests, never by the running API.
TEST_ONLY = {"VYSKAR_TEST_DATABASE_URL", "VYSKAR_TEST_NUMBER"}
READ = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|env_int|os\.environ\[)\(?\s*["']([A-Z][A-Z0-9_]+)["']"""
)
# Read by LangChain itself, not by Vyskar's code.
LANGSMITH = {"LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"}


def names_the_backend_reads() -> set[str]:
    """Settings fields, plus every name read from the environment in code."""
    read = {name.upper() for name in Settings.model_fields}
    for folder in SOURCE_DIRS:
        for path in (BACKEND / folder).rglob("*.py"):
            read |= set(READ.findall(path.read_text()))
    return read - TEST_ONLY


def example_names() -> set[str]:
    """Every NAME in .env.example, set or commented out."""
    names = set()
    for line in EXAMPLE.read_text().splitlines():
        match = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", line)
        if match:
            names.add(match.group(1))
    return names


def test_settings_load_from_the_example(monkeypatch):
    # Only the example counts: settings from the shell must not fill gaps.
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    settings = Settings(_env_file=EXAMPLE)
    assert settings.builder_mode == "pipeline"
    assert settings.graph_recursion_limit > 0


def test_every_required_setting_is_set_not_commented():
    set_lines = {
        line.split("=", 1)[0]
        for line in EXAMPLE.read_text().splitlines()
        if re.match(r"^[A-Z][A-Z0-9_]+=", line)
    }
    fields = Settings.model_fields.items()
    required = {name.upper() for name, field in fields if field.is_required()}
    assert required <= set_lines, sorted(required - set_lines)


def test_example_names_every_setting_the_backend_reads():
    missing = names_the_backend_reads() - example_names()
    assert not missing, f"add to backend/.env.example: {sorted(missing)}"


def test_example_names_nothing_the_backend_ignores():
    # PLANNER_PROVIDER once sat here, read by nothing, while the settings it
    # meant (ARCHITECT_*, TEST_PLANNER_*) were missing.
    unknown = example_names() - names_the_backend_reads() - LANGSMITH
    assert not unknown, f"nothing reads these: {sorted(unknown)}"
