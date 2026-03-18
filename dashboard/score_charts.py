"""Score progression charts using matplotlib → base64 PNG."""

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.settings import PERSONA_ARCHETYPES
from core.models import AgentVersion


def generate_score_chart(versions: list[AgentVersion]) -> str:
    """Generate a score progression chart as a base64-encoded PNG.

    Shows one line per persona + aggregate (bold), X=generation, Y=score.
    Only includes promoted/base versions (the champion lineage).
    """
    # Filter to champion lineage only
    lineage = [v for v in versions if v.status in ("promoted", "base") and v.scores]
    lineage.sort(key=lambda v: v.generation)

    if not lineage:
        return ""

    gens = [v.generation for v in lineage]

    fig, ax = plt.subplots(figsize=(10, 5))

    for persona in PERSONA_ARCHETYPES:
        scores = [v.scores.per_persona[persona].weighted_total for v in lineage]
        ax.plot(gens, scores, marker="o", label=persona, alpha=0.7)

    aggregate = [v.scores.aggregate for v in lineage]
    ax.plot(gens, aggregate, marker="s", label="AGGREGATE", linewidth=3, color="black")

    ax.set_xlabel("Generation")
    ax.set_ylabel("Score")
    ax.set_title("Score Progression Across Generations")
    ax.legend(loc="upper left")
    ax.set_ylim(0, 5)
    ax.grid(True, alpha=0.3)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
