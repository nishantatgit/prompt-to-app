"""The frontend keeps its own copies of a few limits the API enforces, so the
app can stop typing at the limit and say why. If a copy drifts, the app lets
people type text the API then refuses (or hides a bonus they earned). This
reads the frontend's constants and checks them against the server's."""

import re
from pathlib import Path

import pytest

from api import feedback, routes

LIB = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"


def frontend_constant(file: str, name: str) -> int:
    path = LIB / file
    if not path.exists():
        pytest.skip(f"{path} is not in this checkout")
    match = re.search(rf"export const {name} = (\d+)", path.read_text())
    assert match, f"{name} is no longer a number in frontend/src/lib/{file}"
    return int(match.group(1))


def test_prompt_limit_matches():
    assert frontend_constant("prompt.js", "MAX_PROMPT_CHARS") == routes.MAX_PROMPT_CHARS


def test_feedback_limit_matches():
    assert frontend_constant("limits.js", "MAX_FEEDBACK_CHARS") == feedback.MAX_FEEDBACK_CHARS


def test_feedback_bonus_minimum_matches():
    assert (
        frontend_constant("limits.js", "FEEDBACK_BONUS_MIN_CHARS")
        == feedback.MIN_MESSAGE_FOR_BONUS
    )
