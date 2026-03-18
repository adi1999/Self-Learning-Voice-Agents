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


def load_base_prompt(path: str | Path) -> dict[str, str]:
    """Load the base prompt sections from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    expected = {"identity", "objective", "compliance", "opening", "strategy", "closing"}
    missing = expected - set(data.keys())
    if missing:
        raise ValueError(f"Base prompt missing sections: {missing}")
    return {k: data[k] for k in expected}
