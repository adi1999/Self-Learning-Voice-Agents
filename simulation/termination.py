"""End-of-conversation detection: [END:reason] signals, max turns, edge cases."""

import re

VALID_REASONS = {"agreed_to_pay", "hung_up", "asked_to_stop", "callback_agreed"}
END_PATTERN = re.compile(r"\[END:(\w+)\]")

# Map termination reasons to conversation outcomes
REASON_TO_OUTCOME = {
    "agreed_to_pay": "success",
    "hung_up": "rejection",
    "asked_to_stop": "rejection",
    "callback_agreed": "success",
}


def check_termination(response: str) -> str | None:
    """Check if a response contains an [END:reason] signal. Returns outcome or None."""
    match = END_PATTERN.search(response)
    if match:
        reason = match.group(1)
        if reason in VALID_REASONS:
            return REASON_TO_OUTCOME.get(reason, "rejection")
    return None


def strip_termination_signal(response: str) -> str:
    """Remove [END:reason] from response text, returning clean dialogue."""
    return END_PATTERN.sub("", response).strip()
