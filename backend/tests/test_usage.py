import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult

from agents.usage import UsageMeter, cost_usd
from api import jobs


def reply(
    model="claude-sonnet-5-5-20260915", input_tokens=12_000, read=8_000, write=1_000, output=2_000
):
    return AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output,
            "total_tokens": input_tokens + output,
            "input_token_details": {"cache_read": read, "cache_creation": write},
        },
        response_metadata={"model_name": model},
    )


class Metered(BaseChatModel):
    """A model that answers with fixed token counts, like ChatAnthropic does."""

    @property
    def _llm_type(self):
        return "metered"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=reply())])


def test_every_reply_is_counted_through_the_models_callbacks():
    meter = UsageMeter()
    model = Metered(callbacks=[meter])
    model.invoke("hi")
    model.invoke("again")
    usage = meter.summary()
    assert usage["calls"] == 2
    # input_tokens includes the cached ones; each kind is counted once
    assert usage["input_tokens"] == 2 * 3_000
    assert usage["cache_read_tokens"] == 2 * 8_000
    assert usage["cache_write_tokens"] == 2 * 1_000
    assert usage["output_tokens"] == 2 * 2_000


def test_cost_uses_each_kind_of_token_at_its_own_price():
    counts = {
        "input_tokens": 1_000_000,
        "cache_write_tokens": 0,
        "cache_read_tokens": 1_000_000,
        "output_tokens": 100_000,
    }
    # Sonnet 5.5: $2 input, $0.20 cache read, $10 output, per million
    assert cost_usd("claude-sonnet-5-5", counts) == 2.0 + 0.2 + 1.0
    assert cost_usd("claude-sonnet-5-5-20260915", counts) == 3.2
    assert cost_usd("gpt-6.1-sol", counts) is None


def test_a_build_with_an_unpriced_model_says_its_cost_is_partial():
    meter = UsageMeter()
    meter.on_llm_end(LLMResult(generations=[[ChatGeneration(message=reply())]]))
    meter.on_llm_end(LLMResult(generations=[[ChatGeneration(message=reply(model="gpt-6.1-sol"))]]))
    usage = meter.summary()
    assert usage["models"]["gpt-6.1-sol"]["cost_usd"] is None
    assert usage["cost_usd"] == usage["models"]["claude-sonnet-5-5-20260915"]["cost_usd"]
    assert usage["complete"] is False


def test_the_job_shows_and_logs_its_cost(capsys):
    meter = UsageMeter()
    meter.on_llm_end(LLMResult(generations=[[ChatGeneration(message=reply())]]))
    jobs.create_job("j-usage", "A notes app", meter=meter)
    job = jobs.get_job("j-usage")
    view = jobs.public_view(job)
    assert view["usage"]["calls"] == 1 and view["usage"]["cost_usd"] > 0
    jobs._log_usage(job)
    record = json.loads(capsys.readouterr().out)
    assert record["event"] == "build_cost" and record["job_id"] == "j-usage"
    assert record["calls"] == 1 and record["cost_usd"] > 0


def test_jobs_without_a_meter_show_no_usage():
    jobs.create_job("j-none", "p")
    assert jobs.public_view(jobs.get_job("j-none"))["usage"] is None
