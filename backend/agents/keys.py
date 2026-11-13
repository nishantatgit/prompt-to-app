"""Checks a user's API key before a build starts, and turns key and billing
problems into messages the user can act on.

A bad key or an account without credit is the user's to fix, not Vyskar's,
so neither may show up as an internal error halfway through a build.
"""

import anthropic
import openai

PROVIDER_NAMES = {"anthropic": "Anthropic", "openai": "OpenAI"}
AUTH_ERRORS = (anthropic.AuthenticationError, openai.AuthenticationError)
BILLING_PAGES = {
    "anthropic": "console.anthropic.com/settings/billing",
    "openai": "platform.openai.com/settings/organization/billing",
}

# The cheapest model call that still needs credit: one token in, one out.
# Listing models is free, so it cannot tell whether the account has credit.
CREDIT_CHECK_MODEL = "claude-haiku-5-5"


class KeyRejected(Exception):
    pass


def rejected_message(provider: str) -> str:
    name = PROVIDER_NAMES.get(provider, provider)
    return f"Your {name} key was rejected. Check it in settings, or create a new one."


def no_credit_message(provider: str) -> str:
    name = PROVIDER_NAMES.get(provider, provider)
    return f"Your {name} account has no credit left. Add credit at {BILLING_PAGES[provider]}, then build again."


def _provider_of(error: Exception) -> str | None:
    if isinstance(error, anthropic.APIError):
        return "anthropic"
    if isinstance(error, openai.APIError):
        return "openai"
    return None


def is_no_credit(error: Exception) -> bool:
    if isinstance(error, anthropic.BadRequestError):
        return "credit balance" in str(error).lower()
    if isinstance(error, openai.RateLimitError):
        return getattr(error, "code", None) == "insufficient_quota" or "insufficient_quota" in str(error)
    return False


def check_key(provider: str, api_key: str, timeout: float = 10) -> None:
    """Raise KeyRejected when the key is invalid or its account has no credit.

    Any other failure, such as a timeout or an outage at the provider, is not
    the key's fault, so the build is allowed to go ahead and report its own
    error.
    """
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
            client.models.list(limit=1)
            client.messages.create(
                model=CREDIT_CHECK_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "ok"}],
            )
        elif provider == "openai":
            client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
            client.models.list()
    except AUTH_ERRORS as error:
        raise KeyRejected(rejected_message(provider)) from error
    except Exception as error:
        if is_no_credit(error):
            raise KeyRejected(no_credit_message(provider)) from error
        return


def user_error_reason(error: Exception) -> str | None:
    """The job's failure reason when the user's key or account stops a build
    midway, or None for any other error."""
    provider = _provider_of(error)
    if provider is None:
        return None
    if isinstance(error, AUTH_ERRORS):
        return "key rejected: " + rejected_message(provider)
    if is_no_credit(error):
        return "no credit: " + no_credit_message(provider)
    return None


