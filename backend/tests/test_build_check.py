from agents.build_check import python_errors


def test_no_api_folder_means_no_errors(tmp_path):
    assert python_errors(tmp_path) == ""


def test_valid_python_passes(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "index.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    assert python_errors(tmp_path) == ""


def test_syntax_error_is_reported_with_file_and_line(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "index.py").write_text("def broken(:\n    pass\n")
    errors = python_errors(tmp_path)
    assert "api/index.py:1" in errors


def test_compiling_writes_no_cache_files(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "index.py").write_text("x = 1\n")
    python_errors(tmp_path)
    assert not (tmp_path / "api" / "__pycache__").exists()
