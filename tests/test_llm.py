"""Tests for retrying temporary AI failures. Run with:  python -m pytest

GeminiClient is tested without Google: we replace its one network method
(_call) with our own, and replace sleeping with a list that records waits.
"""
import pytest

from copilot.llm import GeminiClient, LLMError


class FakeApiError(Exception):
    """Looks like Google's errors: carries an HTTP status code."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def make_client(outcomes):
    """A GeminiClient whose requests play back the given outcomes in order.

    Each outcome is either text to return or an exception to raise.
    """
    waits = []
    client = GeminiClient(api_key="test-key", sleep=waits.append)
    calls = iter(outcomes)

    def fake_call(system, prompt):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client._call = fake_call
    return client, waits


def test_success_first_time_does_not_wait():
    client, waits = make_client(['{"decision": "needs_review"}'])
    assert client.complete_json("s", "p") == {"decision": "needs_review"}
    assert waits == []


def test_busy_model_is_retried_then_succeeds():
    client, waits = make_client([FakeApiError(503), FakeApiError(503), '{"ok": true}'])
    assert client.complete_json("s", "p") == {"ok": True}
    assert waits == [2, 4]


def test_gives_up_after_all_retries():
    client, waits = make_client([FakeApiError(503)] * 4)
    with pytest.raises(LLMError):
        client.complete_json("s", "p")
    assert waits == [2, 4, 8]


def test_permanent_errors_are_not_retried():
    client, waits = make_client([FakeApiError(404)])
    with pytest.raises(LLMError):
        client.complete_json("s", "p")
    assert waits == []
