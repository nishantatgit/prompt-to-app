import importlib

from fastapi.testclient import TestClient

import api.main
from api.main import DEFAULT_CORS_ORIGINS, cors_origins


def test_one_origin_is_kept_as_written():
    assert cors_origins("https://app.vyskar.com") == ["https://app.vyskar.com"]


def test_spaces_after_commas_are_dropped():
    assert cors_origins("https://app.vyskar.com, https://vyskar.com") == [
        "https://app.vyskar.com",
        "https://vyskar.com",
    ]


def test_a_trailing_slash_is_dropped():
    # Browsers send the origin without a path, so "https://vyskar.com/" never matched.
    assert cors_origins("https://vyskar.com/") == ["https://vyskar.com"]


def test_blank_entries_are_skipped():
    assert cors_origins("https://app.vyskar.com,,") == ["https://app.vyskar.com"]


def test_unset_or_blank_falls_back_to_the_dev_server():
    assert cors_origins(None) == [DEFAULT_CORS_ORIGINS]
    assert cors_origins("") == [DEFAULT_CORS_ORIGINS]
    assert cors_origins(" , ") == [DEFAULT_CORS_ORIGINS]


def test_the_second_site_after_a_space_may_call_the_api(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.vyskar.com, https://vyskar.com/")
    app = importlib.reload(api.main).app
    response = TestClient(app).options(
        "/api/build",
        headers={
            "Origin": "https://vyskar.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://vyskar.com"
