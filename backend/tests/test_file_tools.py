import pytest

from tools.file_tools import make_file_tools
from tools.sandbox import Sandbox


@pytest.fixture
def tools(tmp_path):
    root = tmp_path / "job"
    root.mkdir()
    return {t.name: t for t in make_file_tools(Sandbox(root))}


def test_names(tools):
    assert set(tools) == {"write_file", "read_file", "edit_file", "list_files"}


def test_schemas_list_the_arguments(tools):
    assert set(tools["write_file"].args) == {"path", "content"}
    assert set(tools["edit_file"].args) == {"path", "old", "new"}
    assert set(tools["read_file"].args) == {"path"}
    assert tools["list_files"].args == {}


def test_every_tool_has_a_description(tools):
    assert all(t.description for t in tools.values())


def test_tools_change_the_workspace(tools):
    tools["write_file"].invoke({"path": "src/App.jsx", "content": "a b c"})
    tools["edit_file"].invoke({"path": "src/App.jsx", "old": "b", "new": "B"})
    assert tools["read_file"].invoke({"path": "src/App.jsx"}) == "a B c"
    assert tools["list_files"].invoke({}) == "src/App.jsx"


def test_errors_come_back_as_text(tools):
    answer = tools["read_file"].invoke({"path": "missing.jsx"})
    assert answer == "Error: File 'missing.jsx' does not exist."

    answer = tools["write_file"].invoke({"path": "../escape.txt", "content": "x"})
    assert answer.startswith("Error:") and "outside" in answer


def test_tool_call_format(tools):
    # The loop passes the model's tool call straight through, like this.
    call = {
        "name": "write_file",
        "args": {"path": "a.txt", "content": "hi"},
        "id": "1",
        "type": "tool_call",
    }
    message = tools["write_file"].invoke(call)
    assert message.tool_call_id == "1"
    assert "Wrote a.txt" in message.content
