import pytest

from tools.sandbox import Sandbox, ToolError


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path / "job"
    root.mkdir()
    return Sandbox(root)


def test_write_then_read(sandbox):
    sandbox.write_file("src/App.jsx", "hello")
    assert sandbox.read_file("src/App.jsx") == "hello"


def test_write_creates_folders(sandbox):
    sandbox.write_file("src/components/Card.jsx", "x")
    assert (sandbox.root / "src" / "components" / "Card.jsx").is_file()


def test_read_missing_file(sandbox):
    with pytest.raises(ToolError, match="does not exist"):
        sandbox.read_file("src/Nope.jsx")


def test_edit_replaces_unique_text(sandbox):
    sandbox.write_file("a.txt", "one two three")
    sandbox.edit_file("a.txt", "two", "2")
    assert sandbox.read_file("a.txt") == "one 2 three"


def test_edit_fails_when_text_missing(sandbox):
    sandbox.write_file("a.txt", "one")
    with pytest.raises(ToolError, match="not found"):
        sandbox.edit_file("a.txt", "two", "2")


def test_edit_fails_when_text_repeated(sandbox):
    sandbox.write_file("a.txt", "x x")
    with pytest.raises(ToolError, match="2 times"):
        sandbox.edit_file("a.txt", "x", "y")
    assert sandbox.read_file("a.txt") == "x x"


@pytest.mark.parametrize("path", ["../escape.txt", "src/../../escape.txt", "/etc/passwd"])
def test_rejects_paths_outside_workspace(sandbox, path):
    with pytest.raises(ToolError, match="outside"):
        sandbox.write_file(path, "bad")


def test_list_hides_packages_and_build_output(sandbox):
    sandbox.write_file("src/App.jsx", "a")
    sandbox.write_file("node_modules/react/index.js", "b")
    sandbox.write_file("dist/index.html", "c")
    sandbox.write_file("test-results/x.txt", "d")
    assert sandbox.list_files() == "src/App.jsx"


def test_list_empty_project(sandbox):
    assert sandbox.list_files() == "(empty project)"


def test_works_on_a_real_workspace(tmp_path):
    from tools.workspace import create_workspace

    job_dir = create_workspace(tmp_path, "job-1")
    sandbox = Sandbox(job_dir)
    assert "src/App.jsx" in sandbox.list_files().splitlines()
    assert "package.json" in sandbox.list_files().splitlines()
