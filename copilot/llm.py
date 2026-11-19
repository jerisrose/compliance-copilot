"""The connection to the AI model, kept separate from everything else.

The rest of the project never talks to Google directly. It talks to the small
LLMClient "interface" below. That means:

  * switching to Claude or OpenAI later is a new class here, with no change
    to the screening or review code;
  * tests can use a fake model that answers instantly, costs nothing and
    always gives the same answer.

This is the same idea as programming to an interface in Java.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Protocol

# python-dotenv reads the .env file and puts its lines into the environment,
# so os.environ["GEMINI_API_KEY"] works without the key ever being in code.
from dotenv import load_dotenv

# Find .env by its exact location instead of letting the library search for
# it. The search depends on how Python was started, and with "python -c"
# it could miss the file.
#   __file__          the full path of this file (.../copilot/llm.py)
#   .resolve()        turns it into a complete, absolute path
#   .parent.parent    goes up two levels: copilot/ -> the project folder
#   / ".env"          Path objects join with "/", on Windows too
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# The model can be changed in .env with a line like  GEMINI_MODEL=gemini-3.5-flash
# Google renames models often; the list available to your key is shown in
# Google AI Studio.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

# Some failures are temporary and worth retrying:
#   429 = too many requests (free-tier rate limit)
#   500 = server error
#   503 = model overloaded ("high demand")
#   504 = timed out
# Others, such as 400 (bad request) or 404 (model not found), will fail the
# same way every time, so retrying them would only waste time.
RETRYABLE_CODES = {429, 500, 503, 504}

# Wait 2 seconds, then 4, then 8 before giving up. Doubling the wait each
# time is called "exponential backoff"; it gives a busy service room to
# recover instead of hammering it.
RETRY_DELAYS = [2, 4, 8]

# Give up on any single request after this many seconds. Without a limit,
# the Google library will wait for an answer forever.
REQUEST_TIMEOUT_SECONDS = 30


class LLMError(Exception):
    """Raised when the model can't be reached or gives an unusable answer."""


# A Protocol is Python's closest thing to a Java interface: any class that
# has a matching method counts as an LLMClient, without having to say
# "implements". (Python checks this only when you run a type checker.)
class LLMClient(Protocol):
    def complete_json(self, system: str, prompt: str) -> dict:
        """Send instructions plus a prompt; return the model's JSON answer."""
        ...


class GeminiClient:
    """LLMClient for Google's Gemini models (free tier available)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        # The function used to wait. Real runs use time.sleep; tests pass in
        # a fake that doesn't actually wait, so they stay instant.
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.sleep = sleep
        # "a or b" picks the first value that isn't empty, so an argument
        # passed in wins, then the .env setting, then the default.
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        if not self.api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Add it to the .env file in the project folder."
            )

        # Imported here rather than at the top of the file, so the tests
        # (which use a fake client) work even without the Google library.
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=self.api_key,
            # The library measures this in milliseconds, hence * 1000.
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000),
        )

    def complete_json(self, system: str, prompt: str) -> dict:
        # The first try has no wait before it; each retry waits a bit longer.
        # [0] + RETRY_DELAYS joins two lists: [0, 2, 4, 8].
        waits = [0] + RETRY_DELAYS
        for attempt, wait in enumerate(waits, start=1):
            if wait:
                self.sleep(wait)
            try:
                return parse_json(self._call(system, prompt))
            except Exception as e:  # network problems, bad key, overload...
                is_last = attempt == len(waits)
                if is_retryable(e) and not is_last:
                    continue  # go round the loop again
                raise LLMError(f"Gemini request failed: {e}") from e
        # Python can't tell the loop always returns or raises, so this line
        # keeps the function's promise to return something. It never runs.
        raise LLMError("Gemini request failed.")

    def _call(self, system: str, prompt: str) -> str | None:
        """One request to Gemini; returns the raw text of the answer."""
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                # The standing instructions for the model, separate
                # from the case it is being asked about.
                system_instruction=system,
                # Ask for JSON only, so the answer can be read by code.
                response_mime_type="application/json",
            ),
        )
        return response.text


def is_retryable(error: Exception) -> bool:
    """True if the error is a temporary one worth trying again."""
    # Google's errors carry the HTTP status number in a "code" attribute.
    # getattr(..., None) returns None instead of crashing if it isn't there.
    return getattr(error, "code", None) in RETRYABLE_CODES


def parse_json(text: str | None) -> dict:
    """Turn the model's text into a dictionary, or raise LLMError."""
    if not text:
        raise LLMError("The model returned an empty answer.")
    cleaned = text.strip()
    # Some models wrap JSON in ```json ... ``` fences; remove them if present.
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json"):]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"The model's answer was not valid JSON: {text[:200]}") from e
    if not isinstance(data, dict):
        raise LLMError("The model's answer was JSON, but not an object.")
    return data
