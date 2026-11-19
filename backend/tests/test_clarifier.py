from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agents import clarifier
from api import jobs, routes


class Canned(BaseChatModel):
    """Answers every call with fixed JSON, like a model in json_schema mode."""

    reply: str = '{"questions": []}'

    @property
    def _llm_type(self):
        return "canned"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply))])

    def with_structured_output(self, schema, include_raw=False, **kwargs):
        def parse(messages):
            text = self.invoke(messages).content
            try:
                return {
                    "raw": text,
                    "parsed": schema.model_validate_json(text),
                    "parsing_error": None,
                }
            except Exception as error:
                return {"raw": text, "parsed": None, "parsing_error": error}

        from langchain_core.runnables import RunnableLambda

        return RunnableLambda(parse)


TWO = (
    '{"questions": ['
    '{"question": "Who will use it?", "options": ["Just me", "My whole team", "I\'m not sure"]},'
    '{"question": "Keep data online?", "options": ["Yes", "No"]},'
    '{"question": "A third one?", "options": ["a", "b"]}]}'
)


def test_questions_are_capped_and_cleaned():
    questions = clarifier.ask(Canned(reply=TWO), "A team task board")
    assert [q["question"] for q in questions] == ["Who will use it?", "Keep data online?"]
    # "I'm not sure" is added by the app, not taken from the model
    assert questions[0]["options"] == ["Just me", "My whole team"]


def test_a_clear_request_gets_no_questions():
    assert clarifier.ask(Canned(), "A tip calculator") == []


def test_a_broken_reply_means_no_questions():
    assert clarifier.ask(Canned(reply="not json"), "x") == []


def test_answers_are_added_to_the_request():
    prompt = clarifier.with_answers(
        "A task board",
        [
            {"question": "Who will use it?", "answer": "My whole team"},
            {"question": "Keep data online?", "answer": "I'm not sure"},
            {"question": "Skipped?", "answer": ""},
        ],
    )
    assert prompt == (
        "A task board\n\nMore details:\n"
        "- Who will use it? My whole team\n"
        "- Keep data online? Not sure, choose what fits best."
    )
    assert clarifier.with_answers("A timer", []) == "A timer"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = SimpleNamespace(
        workspaces_dir=tmp_path,
        builder_mode="loop",
        graph_recursion_limit=50,
        guard_provider="anthropic",
        guard_model="claude-haiku-5-5",
        api_key_for=lambda provider: "sk-ant-vyskar",
    )
    for name in ("DATA_DIR", "ALLOW_OWN_KEYS", "ALLOW_SERVER_KEYS", "STUB_LLM", "RAZORPAY_KEY_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "0")
    monkeypatch.setattr(routes, "_ledger", None)
    routes._clarify_hits.clear()
    used = []
    monkeypatch.setattr(
        routes,
        "create_llm",
        lambda provider, model, key: used.append((provider, model, key)) or Canned(reply=TWO),
    )
    submitted = []
    monkeypatch.setattr(routes, "check_key", lambda provider, key: None)
    monkeypatch.setattr(routes, "check_rate_limit", lambda request: None)
    monkeypatch.setattr(routes, "has_capacity", lambda: True)
    monkeypatch.setattr(routes, "make_models", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "build_graph", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "submit", lambda *a: submitted.append(a))
    app.dependency_overrides[routes.get_settings] = lambda: settings
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    c = TestClient(app, headers={"X-Vyskar-Visitor": "v1"})
    c.used, c.submitted = used, submitted
    yield c
    app.dependency_overrides.clear()
    jobs.TRIAL_FINISHED_HOOKS.clear()


def test_clarify_uses_the_cheap_model_with_your_key(client):
    body = {"prompt": "A team task board", "provider": "anthropic", "api_key": "sk-own"}
    response = client.post("/api/clarify", json=body).json()
    assert len(response["questions"]) == 2
    assert client.used == [("anthropic", "claude-haiku-5-5", "sk-own")]


def test_clarify_on_free_builds_uses_vyskars_key(client, monkeypatch):
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "2")
    client.post("/api/clarify", json={"prompt": "A task board", "provider": "openai"})
    assert client.used == [("anthropic", "claude-haiku-5-5", "sk-ant-vyskar")]


def test_without_any_way_to_build_there_are_no_questions(client):
    response = client.post("/api/clarify", json={"prompt": "A task board", "provider": "anthropic"})
    assert response.json() == {"questions": []}
    assert client.used == []


def test_changes_to_an_app_skip_questions(client):
    body = {"prompt": "Add dark mode", "provider": "anthropic", "api_key": "k", "app": "notes-1"}
    assert client.post("/api/clarify", json=body).json() == {"questions": []}


def test_clarify_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(routes, "CLARIFY_PER_HOUR", 1)
    body = {"prompt": "A task board", "provider": "anthropic", "api_key": "k"}
    assert client.post("/api/clarify", json=body).json()["questions"]
    assert client.post("/api/clarify", json=body).json() == {"questions": []}


def test_the_build_gets_the_answers(client):
    body = {
        "prompt": "A task board",
        "provider": "anthropic",
        "api_key": "k",
        "answers": [{"question": "Who will use it?", "answer": "My whole team"}],
    }
    assert client.post("/api/build", json=body).status_code == 202
    prompt = client.submitted[0][2]
    assert prompt.endswith("- Who will use it? My whole team")
    too_many = {**body, "answers": body["answers"] * 3}
    assert client.post("/api/build", json=too_many).status_code == 422
