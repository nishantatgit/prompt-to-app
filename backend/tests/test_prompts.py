from agents.architect import ARCHITECT_PROMPT
from agents.builder import PROMPT as BUILDER_PROMPT


def test_architect_gets_the_planning_guide():
    assert "Visual design: planning" in ARCHITECT_PROMPT
    assert "Neutral: Inter" not in ARCHITECT_PROMPT


def test_builder_gets_the_building_guide():
    assert "Visual design: building" in BUILDER_PROMPT
    assert "no sideways scrolling" in BUILDER_PROMPT


def test_generic_card_and_font_defaults_are_gone():
    assert "Group related content in cards" not in BUILDER_PROMPT
    assert "slight lift on hover" not in BUILDER_PROMPT
    assert '"Inter"' not in BUILDER_PROMPT


def test_build_loop_gets_the_building_guide():
    from agents.build_loop import PROMPT as LOOP_PROMPT

    assert "Visual design: building" in LOOP_PROMPT
    assert "edit_file" in LOOP_PROMPT


def test_guides_cover_light_and_dark():
    assert "light and a dark version" in ARCHITECT_PROMPT
    assert "prefers-color-scheme: dark" in BUILDER_PROMPT
