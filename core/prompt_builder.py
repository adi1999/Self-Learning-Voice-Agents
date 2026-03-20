"""Assembles prompt sections into a single system prompt string."""

from pathlib import Path

import yaml


def build_prompt(sections: dict[str, str]) -> str:
    """Assembles prompt sections into a single system prompt string."""
    return f"""## IDENTITY
{sections['identity']}

## OBJECTIVE
{sections['objective']}

## COMPLIANCE RULES
{sections['compliance']}

## OPENING THE CALL
{sections['opening']}

## STRATEGY & OBJECTION HANDLING
{sections['strategy']}

## CLOSING THE CALL
{sections['closing']}"""


def build_dynamic_prompt(sections: dict[str, str], persona_type: str) -> str:
    """Build prompt with persona-specific learned tactics injected after strategy."""
    from config.settings import MAX_TACTICS_PER_PROMPT
    from core.playbook import get_tactics_for_persona

    base = build_prompt(sections)
    tactics = get_tactics_for_persona(persona_type, limit=MAX_TACTICS_PER_PROMPT)
    if not tactics:
        return base

    tactic_lines = "\n".join(f"- {t.tactic}" for t in tactics)
    learned_section = f"\n\n## LEARNED TACTICS\nThese tactics have proven effective with this type of borrower:\n{tactic_lines}"
    return base + learned_section


def load_voice_overlay(path: str | Path = "prompts/voice_overlay.yaml") -> str:
    """Load the voice-specific prompt overlay."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["voice_context"]


def build_voice_prompt(sections: dict[str, str]) -> str:
    """Build the full voice prompt: base sections + voice overlay."""
    base = build_prompt(sections)
    overlay = load_voice_overlay()
    return base + "\n\n" + overlay


def load_base_prompt(path: str | Path) -> dict[str, str]:
    """Load the base prompt sections from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    expected = {"identity", "objective", "compliance", "opening", "strategy", "closing"}
    missing = expected - set(data.keys())
    if missing:
        raise ValueError(f"Base prompt missing sections: {missing}")
    return {k: data[k] for k in expected}
