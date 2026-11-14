from agents.architect import ARCHITECT_PROMPT
from agents.builder import PROMPT as BUILDER_PROMPT


def test_architect_gets_the_planning_guide():
    assert "Visual design: planning in Vyskar" in ARCHITECT_PROMPT
    assert "Neutral: Inter" not in ARCHITECT_PROMPT


def test_builder_gets_the_building_guide():
    assert "Visual design: building in Vyskar" in BUILDER_PROMPT
    assert "no sideways scrolling" in BUILDER_PROMPT


def test_generic_card_and_font_defaults_are_gone():
    assert "Group related content in cards" not in BUILDER_PROMPT
    assert "slight lift on hover" not in BUILDER_PROMPT
    assert '"Inter"' not in BUILDER_PROMPT


def test_build_loop_gets_the_building_guide():
    from agents.build_loop import PROMPT as LOOP_PROMPT

    assert "Visual design: building in Vyskar" in LOOP_PROMPT
    assert "edit_file" in LOOP_PROMPT


def test_frontend_design_skill_is_verbatim():
    from pathlib import Path

    skill = (Path(__file__).parent.parent / "agents/prompts/frontend_design.md").read_text()
    assert skill.startswith("# Frontend Design\n")
    assert "Restraint and self-critique" in skill
    from agents.build_loop import PROMPT as LOOP_PROMPT

    for prompt in (ARCHITECT_PROMPT, BUILDER_PROMPT, LOOP_PROMPT):
        assert skill in prompt


def test_build_loop_knows_how_to_use_supabase():
    from agents.build_loop import PROMPT as LOOP_PROMPT

    assert "import.meta.env.VITE_SUPABASE_ANON_KEY" in LOOP_PROMPT
    assert "supabase/migrations/*.sql" in LOOP_PROMPT
    assert "api/index.py is a FastAPI app" in LOOP_PROMPT


def test_guides_cover_light_and_dark():
    assert "light and a dark version" in ARCHITECT_PROMPT
    assert "prefers-color-scheme: dark" in BUILDER_PROMPT


def test_test_planner_checks_saved_data_inside_its_list():
    from pathlib import Path

    rules = (Path(__file__).parent.parent / "agents/prompts/test_planner.md").read_text()
    assert "getByRole('list', { name: 'Entries' }).getByText(message)" in rules
    assert "never with a page wide getByText" in " ".join(rules.split())


def test_build_loop_and_test_planner_know_how_logins_work():
    from pathlib import Path

    prompts = Path(__file__).parent.parent / "agents/prompts"
    loop = " ".join((prompts / "build_loop.md").read_text().split())
    planner = " ".join((prompts / "test_planner.md").read_text().split())
    assert "When needs_auth is true:" in loop
    assert "Never show \"check your email\"" in loop
    assert "user_id uuid not null default auth.uid()" in loop
    assert "Vyskar turns off email confirmation" in planner
    assert "@gmail.com" in planner
