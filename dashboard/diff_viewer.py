"""Prompt section diffs between generations using difflib."""

import difflib

from core.models import AgentVersion


def generate_diff(parent: AgentVersion, child: AgentVersion) -> dict:
    """Generate a diff for the mutated section between parent and child.

    Returns dict with keys: section, rationale, diff_html, before, after.
    """
    section = child.mutation_target
    if not section:
        return {}

    before = parent.prompt_sections.get(section, "")
    after = child.prompt_sections.get(section, "")

    diff_lines = list(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{parent.id}/{section}",
        tofile=f"{child.id}/{section}",
        lineterm="",
    ))

    return {
        "section": section,
        "rationale": child.rationale or "",
        "failure_patterns": child.failure_patterns,
        "diff_text": "\n".join(diff_lines),
        "before": before,
        "after": after,
    }


def generate_all_diffs(versions: list[AgentVersion]) -> list[dict]:
    """Generate diffs for all promoted versions in the lineage."""
    by_id = {v.id: v for v in versions}
    diffs = []

    promoted = sorted(
        [v for v in versions if v.status == "promoted" and v.parent_id],
        key=lambda v: v.generation,
    )

    for child in promoted:
        parent = by_id.get(child.parent_id)
        if parent:
            diff = generate_diff(parent, child)
            if diff:
                diff["child_id"] = child.id
                diff["parent_id"] = parent.id
                diff["generation"] = child.generation
                diffs.append(diff)

    return diffs
