"""Orchestrates full HTML report generation."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config.settings import REPORTS_DIR
from core.archive import list_versions
from dashboard.diff_viewer import generate_all_diffs
from dashboard.score_charts import generate_score_chart
from dashboard.tree_visualizer import generate_mermaid_tree

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report() -> Path:
    """Generate the full HTML evolution report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    versions = list_versions()
    if not versions:
        logger.warning("No versions in archive — generating empty report")

    mermaid = generate_mermaid_tree(versions)
    chart_b64 = generate_score_chart(versions)
    diffs = generate_all_diffs(versions)

    champion = None
    for v in versions:
        if v.status in ("promoted", "base") and v.scores:
            if champion is None or v.scores.aggregate > champion.scores.aggregate:
                champion = v

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    html = template.render(
        mermaid_diagram=mermaid,
        score_chart_b64=chart_b64,
        diffs=diffs,
        versions=versions,
        champion=champion,
    )

    output_path = REPORTS_DIR / "evolution_report.html"
    output_path.write_text(html)
    logger.info(f"Report written to {output_path}")
    return output_path
