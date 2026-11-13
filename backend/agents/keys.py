"""Checks a user's API key before a build starts, and turns a rejected key
into a message the user can act on.

A bad key is the user's problem to fix, not Vyskar's, so it must never show
up as an internal error halfway through a build.
"""

import anthropic
import openai

PROVIDER_NAMES = {"anthropic": "Anthropic", "openai": "OpenAI"}
AUTH_ERRORS = (anthropic.AuthenticationError, openai.AuthenticationError)


class KeyRejected(Exception):
    pass


def rejected_message(provider: str) -> str:
    name = PROVIDER_NAMES.get(provider, provider)
    return f"Your {name} key was rejected. Check it in settings, or create a new one."


def check_key(provider: str, api_key: str, timeout: float = 10) -> None:
    """Raise KeyRejected when the provider says the key is invalid.

    Listing models costs nothing and uses no tokens. Any other failure, such
    as a timeout or an outage at the provider, is not the key's fault, so the
    build is allowed to go ahead and report its own error.
    """
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
            client.models.list(limit=1)
        elif provider == "openai":
            client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
            client.models.list()
    except AUTH_ERRORS as error:
        raise KeyRejected(rejected_message(provider)) from error
    except Exception:
        return


def rejected_reason(error: Exception) -> str | None:
    """The job's failure reason when a key is rejected during a build, or None
    for any other error."""
    if isinstance(error, anthropic.AuthenticationError):
        return "key rejected: " + rejected_message("anthropic")
    if isinstance(error, openai.AuthenticationError):
        return "key rejected: " + rejected_message("openai")
    return None
