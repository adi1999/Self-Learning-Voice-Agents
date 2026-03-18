"""Generate candidate prompt rewrites for a target section."""

import logging
import re

from config.settings import MUTATION_MODEL
from core.llm_client import llm_call
from core.models import AgentVersion, FailurePattern
from core.prompt_builder import build_prompt

logger = logging.getLogger(__name__)

MUTATION_PROMPT = """You are rewriting one section of a debt collection voice agent prompt to address specific failure patterns.

FULL CURRENT PROMPT (for context — do not modify other sections):
{full_prompt}

SECTION TO REWRITE: {section_name}
CURRENT SECTION TEXT:
{current_section_text}

FAILURE ANALYSIS:
{failure_description}

SPECIFIC EXAMPLES OF THE FAILURE:
{examples}

DIRECTION FOR IMPROVEMENT:
{direction}

CONSTRAINTS:
- Keep the same overall structure and approximate length (±20%)
- Do not contradict anything in the COMPLIANCE section
- Include specific, actionable instructions (not vague platitudes)
- The agent should sound human, not robotic
- Preserve anything in the current section that is working well

RESPOND WITH EXACTLY:
RATIONALE: [One paragraph explaining what you changed and why]
---
NEW_SECTION:
[The complete rewritten section text]"""


def _format_examples(pattern: FailurePattern) -> str:
    """Format example turns from a failure pattern."""
    lines = []
    for ex in pattern.example_turns:
        lines.append(f"  Conversation {ex.conversation_id}, Turn {ex.turn_index}: {ex.content}")
    return "\n".join(lines) if lines else "  (no specific examples)"


def _parse_mutation_response(response: str) -> tuple[str, str]:
    """Parse rationale and new section text from mutation response."""
    # Split on the --- separator
    parts = re.split(r"\n---\n", response, maxsplit=1)
    if len(parts) != 2:
        # Fallback: try to find NEW_SECTION marker
        marker = "NEW_SECTION:"
        idx = response.find(marker)
        if idx == -1:
            raise ValueError("Could not parse mutation response — missing --- separator or NEW_SECTION marker")
        rationale = response[:idx].replace("RATIONALE:", "").strip()
        new_section = response[idx + len(marker):].strip()
    else:
        rationale = parts[0].replace("RATIONALE:", "").strip()
        new_section = parts[1].replace("NEW_SECTION:", "").strip()

    return rationale, new_section


async def generate_candidates(
    parent: AgentVersion,
    pattern: FailurePattern,
    num_candidates: int = 2,
) -> list[tuple[str, str, dict[str, str]]]:
    """Generate N candidate rewrites of the target section.

    Returns list of (rationale, section_name, new_prompt_sections) tuples.
    """
    section_name = pattern.target_section.lower()
    full_prompt = build_prompt(parent.prompt_sections)
    current_text = parent.prompt_sections[section_name]
    examples = _format_examples(pattern)

    prompt = MUTATION_PROMPT.format(
        full_prompt=full_prompt,
        section_name=section_name.upper(),
        current_section_text=current_text,
        failure_description=pattern.description,
        examples=examples,
        direction=pattern.suggested_direction,
    )

    candidates = []
    for i in range(num_candidates):
        response = await llm_call(
            system="You are an expert prompt engineer specializing in conversational AI.",
            messages=[{"role": "user", "content": prompt}],
            model=MUTATION_MODEL,
            temperature=0.8,
        )
        rationale, new_section = _parse_mutation_response(response)

        new_sections = dict(parent.prompt_sections)
        new_sections[section_name] = new_section

        candidates.append((rationale, section_name, new_sections))
        logger.info(f"Generated candidate {i+1}/{num_candidates} for [{section_name}]: {rationale[:80]}...")

    return candidates
