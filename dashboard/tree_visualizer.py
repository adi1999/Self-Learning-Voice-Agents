"""Generate Mermaid diagram from the agent version archive DAG."""

from core.models import AgentVersion


def generate_mermaid_tree(versions: list[AgentVersion]) -> str:
    """Generate a Mermaid graph TD diagram showing the evolution tree."""
    lines = ["graph TD"]

    for v in versions:
        score = f"{v.scores.aggregate:.1f}" if v.scores else "?"
        label_parts = [f"{v.id} ({v.status})", f"score: {score}"]
        if v.mutation_target:
            label_parts.append(f"changed: {v.mutation_target.upper()}")
        label = "<br/>".join(label_parts)
        lines.append(f'    {v.id}["{label}"]')

    for v in versions:
        if v.parent_id:
            lines.append(f"    {v.parent_id} --> {v.id}")

    # Style promoted versions green, archived red
    for v in versions:
        if v.status == "promoted":
            lines.append(f"    style {v.id} fill:#2d6a2d,color:#fff")
        elif v.status == "archived":
            lines.append(f"    style {v.id} fill:#6a2d2d,color:#fff")
        elif v.status == "base":
            lines.append(f"    style {v.id} fill:#2d2d6a,color:#fff")

    return "\n".join(lines)
