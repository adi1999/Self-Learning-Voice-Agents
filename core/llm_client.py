"""Thin async wrapper over Anthropic + OpenAI + Google GenAI SDKs for all evolution tasks."""

import asyncio
import contextvars
import json
import logging
from dataclasses import dataclass, field

import anthropic
import openai
from google import genai
from google.genai import types

from config.settings import ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY

logger = logging.getLogger(__name__)

# Suppress noisy Google GenAI AFC logging
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

_anthropic_client: anthropic.AsyncAnthropic | None = None
_openai_client: openai.AsyncOpenAI | None = None
_google_client: genai.Client | None = None

# Limit concurrent API calls to avoid rate limits
_semaphore: asyncio.Semaphore | None = None
_semaphore_loop: asyncio.AbstractEventLoop | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or recreate semaphore bound to the current event loop."""
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(2)
        _semaphore_loop = loop
    return _semaphore


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _get_openai() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _get_google() -> genai.Client:
    global _google_client
    if _google_client is None:
        _google_client = genai.Client(api_key=GOOGLE_API_KEY)
    return _google_client


def _route_model(model: str) -> str:
    """Return provider name for a given model string."""
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if model.startswith("gemini"):
        return "google"
    return "anthropic"


@dataclass
class TokenUsage:
    """Tracks cumulative token usage across all calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0
    errors: int = 0
    _by_model: dict = field(default_factory=dict)

    def record(self, model: str, input_tok: int, output_tok: int) -> None:
        self.input_tokens += input_tok
        self.output_tokens += output_tok
        self.call_count += 1
        if model not in self._by_model:
            self._by_model[model] = {"input": 0, "output": 0, "calls": 0}
        self._by_model[model]["input"] += input_tok
        self._by_model[model]["output"] += output_tok
        self._by_model[model]["calls"] += 1

    def summary(self) -> str:
        lines = [f"Total: {self.call_count} calls, {self.input_tokens} in, {self.output_tokens} out"]
        for model, stats in self._by_model.items():
            lines.append(f"  {model}: {stats['calls']} calls, {stats['input']} in, {stats['output']} out")
        return "\n".join(lines)


usage = TokenUsage()

# --- Per-scope token counter (context var, auto-collected by llm_call) ---
_token_counter: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar(
    "_token_counter", default=None
)


class token_counter:
    """Context manager that accumulates tokens from all llm_call invocations within its scope.

    Usage:
        with token_counter() as tc:
            await llm_call(...)
            await llm_call(...)
        print(tc.input_tokens, tc.output_tokens)
    """

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self._counts: list[int] = [0, 0]  # [input, output] — mutable list shared via contextvar

    def __enter__(self) -> "token_counter":
        self._token = _token_counter.set(self._counts)
        return self

    def __exit__(self, *exc: object) -> None:
        self.input_tokens = self._counts[0]
        self.output_tokens = self._counts[1]
        _token_counter.reset(self._token)

    @property
    def total_tokens(self) -> int:
        return self._counts[0] + self._counts[1]


MAX_RETRIES = 5


async def _call_anthropic(
    system: str, messages: list[dict], model: str, max_tokens: int, temperature: float,
) -> tuple[str, int, int]:
    """Call Anthropic API, return (text, input_tokens, output_tokens)."""
    client = _get_anthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        temperature=temperature,
    )
    return response.content[0].text, response.usage.input_tokens, response.usage.output_tokens


async def _call_openai(
    system: str, messages: list[dict], model: str, max_tokens: int, temperature: float,
) -> tuple[str, int, int]:
    """Call OpenAI API, return (text, input_tokens, output_tokens)."""
    client = _get_openai()
    oai_messages = [{"role": "system", "content": system}] + messages
    response = await client.chat.completions.create(
        model=model,
        messages=oai_messages,
        max_completion_tokens=max_tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content or ""
    in_tok = response.usage.prompt_tokens if response.usage else 0
    out_tok = response.usage.completion_tokens if response.usage else 0
    return text, in_tok, out_tok


async def _call_google(
    system: str, messages: list[dict], model: str, max_tokens: int, temperature: float,
) -> tuple[str, int, int]:
    """Call Google GenAI API, return (text, input_tokens, output_tokens)."""
    client = _get_google()
    # Convert OpenAI-style messages to Gemini contents (assistant → model)
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    response = await client.aio.models.generate_content(
        model=model, contents=contents, config=config,
    )
    in_tok = response.usage_metadata.prompt_token_count or 0
    out_tok = response.usage_metadata.candidates_token_count or 0
    return response.text, in_tok, out_tok


async def llm_call(
    system: str,
    messages: list[dict],
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Make a single LLM call with retries and concurrency control. Routes by model name prefix."""
    provider = _route_model(model)
    call_fn = {"openai": _call_openai, "google": _call_google, "anthropic": _call_anthropic}[provider]

    for attempt in range(MAX_RETRIES):
        try:
            async with _get_semaphore():
                text, in_tok, out_tok = await call_fn(system, messages, model, max_tokens, temperature)
            usage.record(model, in_tok, out_tok)
            # Feed per-scope counter if active
            counts = _token_counter.get()
            if counts is not None:
                counts[0] += in_tok
                counts[1] += out_tok
            await asyncio.sleep(1.5)
            return text
        except (anthropic.RateLimitError, openai.RateLimitError, genai.errors.ClientError) as e:
            usage.errors += 1
            if attempt < MAX_RETRIES - 1:
                wait = 10 * (attempt + 1)
                logger.warning(f"Rate limited (attempt {attempt+1}), waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise
        except (anthropic.APIError, openai.APIError, genai.errors.ServerError) as e:
            usage.errors += 1
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(f"API error: {e}, retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise


def _extract_json(raw: str) -> dict | list:
    """Extract and parse JSON from an LLM response, handling common wrapping."""
    text = raw.strip()

    # Strip markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { or [ and last } or ]
    start = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start == -1:
        raise json.JSONDecodeError("No JSON object found in response", text, 0)

    bracket = "}" if text[start] == "{" else "]"
    end = text.rfind(bracket)
    if end == -1:
        raise json.JSONDecodeError("No closing bracket found", text, start)

    snippet = text[start:end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        # Try fixing common LLM JSON errors: trailing commas, missing commas
        import re
        fixed = re.sub(r',\s*([}\]])', r'\1', snippet)  # remove trailing commas
        fixed = re.sub(r'"\s*\n\s*"', '",\n"', fixed)   # add missing commas between strings
        fixed = re.sub(r'}\s*\n\s*{', '},\n{', fixed)   # add missing commas between objects
        return json.loads(fixed)


MAX_JSON_RETRIES = 3


async def llm_call_json(
    system: str,
    messages: list[dict],
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> dict | list:
    """Make an LLM call and parse the response as JSON. Retries on parse failure."""
    for attempt in range(MAX_JSON_RETRIES + 1):
        raw = await llm_call(system, messages, model, max_tokens, temperature)
        try:
            return _extract_json(raw)
        except (json.JSONDecodeError, ValueError):
            if attempt < MAX_JSON_RETRIES:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}), retrying...")
            else:
                logger.error(f"JSON parse failed after {MAX_JSON_RETRIES + 1} attempts. Raw: {raw[:200]}")
                raise
