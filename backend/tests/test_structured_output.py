import pytest

from agents.analyst import make_analyst
from agents.architect import make_architect
from agents.guard import make_guard
from agents.test_planner import make_test_planner


class Recorder:
    """Records how each agent asks for structured output, then stops."""

    def __init__(self):
        self.calls = []

    def with_structured_output(self, schema, **kwargs):
        self.calls.append((schema.__name__, kwargs))
        raise RuntimeError("recorded")


@pytest.mark.parametrize("make", [make_guard, make_analyst, make_architect, make_test_planner])
def test_agents_use_native_structured_output(make):
    llm = Recorder()
    try:
        make(llm)
    except RuntimeError:
        pass
    if not llm.calls:  # the chain is built on the first call
        with pytest.raises(RuntimeError):
            make(llm)({"prompt": "A timer", "job_id": "x"})
    assert llm.calls, "the agent never asked for structured output"
    assert llm.calls[0][1] == {"include_raw": True, "method": "json_schema"}
