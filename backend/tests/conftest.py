import pytest


@pytest.fixture(autouse=True)
def no_real_server_key_check(monkeypatch):
    """GET /api/trial checks Vyskar's own key with Anthropic. Tests never
    make that call: the key counts as working unless a test says otherwise."""
    from api import routes
    from api.server_key import ServerKeyStatus

    monkeypatch.setattr(routes, "server_key_status", ServerKeyStatus(check=lambda p, k: None))
