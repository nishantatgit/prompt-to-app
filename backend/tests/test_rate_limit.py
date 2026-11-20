import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api import limits


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(limits.time, "monotonic", c)
    monkeypatch.setattr(limits, "BUILDS_PER_HOUR", 3)
    limits._hits.clear()
    yield c
    limits._hits.clear()


def request(ip="1.2.3.4", fly_ip=None):
    headers = [(b"fly-client-ip", fly_ip.encode())] if fly_ip else []
    return Request({"type": "http", "headers": headers, "client": (ip, 5000)})


def test_allows_builds_up_to_the_limit_then_refuses(clock):
    for _ in range(3):
        limits.check_rate_limit(request())
    with pytest.raises(HTTPException) as error:
        limits.check_rate_limit(request())
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "3600"
    assert error.value.detail == "Too many builds from your network. Try again in 60 minutes."


def test_whole_minutes_are_not_rounded_up_an_extra_minute(clock):
    for _ in range(3):
        limits.check_rate_limit(request())
    clock.now += 3600 - 120  # the first build leaves the window in exactly 2 minutes
    with pytest.raises(HTTPException) as error:
        limits.check_rate_limit(request())
    assert error.value.headers["Retry-After"] == "120"
    assert error.value.detail.endswith("Try again in 2 minutes.")


def test_under_a_minute_says_one_minute(clock):
    for _ in range(3):
        limits.check_rate_limit(request())
    clock.now += 3600 - 20
    with pytest.raises(HTTPException) as error:
        limits.check_rate_limit(request())
    assert error.value.headers["Retry-After"] == "20"
    assert error.value.detail.endswith("Try again in 1 minute.")


def test_a_build_is_allowed_again_once_the_oldest_leaves_the_window(clock):
    for _ in range(3):
        limits.check_rate_limit(request())
        clock.now += 10
    clock.now = 1000.0 + 3601
    limits.check_rate_limit(request())  # does not raise


def test_networks_are_counted_separately_by_fly_client_ip(clock):
    for _ in range(3):
        limits.check_rate_limit(request(fly_ip="9.9.9.9"))
    limits.check_rate_limit(request(fly_ip="8.8.8.8"))  # another network, not limited
    with pytest.raises(HTTPException):
        limits.check_rate_limit(request(ip="1.1.1.1", fly_ip="9.9.9.9"))


def test_networks_with_no_recent_build_are_forgotten(clock):
    limits.check_rate_limit(request(fly_ip="5.5.5.5"))
    clock.now += 3601
    limits.check_rate_limit(request(fly_ip="6.6.6.6"))
    assert set(limits._hits) == {"6.6.6.6"}


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(1, "1 minute"), (60, "1 minute"), (61, "2 minutes"), (120, "2 minutes"), (3600, "60 minutes")],
)
def test_wait_message(seconds, text):
    assert limits.wait_message(seconds).endswith(f"Try again in {text}.")
