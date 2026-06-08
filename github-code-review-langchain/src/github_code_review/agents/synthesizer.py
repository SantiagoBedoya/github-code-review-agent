from __future__ import annotations

import logging
import os
import time

from langchain_openai import ChatOpenAI

from github_code_review.agents.prompts import SYNTHESIZER_SYSTEM
from github_code_review.config import settings
from github_code_review.models import AgentReview

logger = logging.getLogger("github_code_review.agents")


_AGENT_LABELS = {
    "seguridad": "🔒 Seguridad",
    "estructuras": "🏗️ Estructuras",
    "calidad": "✨ Calidad",
    "performance": "⚡ Performance",
    "documentacion": "📖 Documentación",
}


def _get_synth_llm() -> ChatOpenAI:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
    )


async def synthesize(all_reviews: dict[str, dict[str, AgentReview]]) -> str:
    """Generates a consolidated Markdown report from all agent reviews across all files."""
    lines = ["## Análisis de archivos modificados\n"]
    for file_path, agent_reviews in all_reviews.items():
        lines.append(f"### `{file_path}`")
        for agent_name, review in agent_reviews.items():
            label = _AGENT_LABELS.get(agent_name, agent_name)

            if "__SKIPPED__" in review.resumen:
                continue
            if "Error" in review.resumen:
                lines.append(f"- **{label}**: ⚠️ {review.resumen}")
                continue
            if not review.issues:
                lines.append(f"- **{label}**: ✅ Sin issues")
            else:
                lines.append(f"- **{label}**: {len(review.issues)} issue(s) encontrados")
                for issue in review.issues:
                    emoji = {"crítica": "🔴", "alta": "🟠", "media": "🟡", "baja": "🟢"}.get(
                        issue.severidad, ""
                    )
                    loc = f" (línea {issue.linea})" if issue.linea else ""
                    lines.append(
                        f"  - {emoji} **[{issue.severidad.capitalize()}]{loc}** "
                        f"{issue.descripcion}"
                    )
                    if issue.sugerencia:
                        lines.append(f"    > 💡 {issue.sugerencia}")
        lines.append("")

    consolidated = "\n".join(lines)
    t0 = time.monotonic()
    logger.info("-> Generating consolidated report…")
    response = await _get_synth_llm().ainvoke([
        ("system", SYNTHESIZER_SYSTEM),
        ("human", consolidated),
    ])
    elapsed = time.monotonic() - t0
    logger.info("-> Synthesizer done  (%.3fs)", elapsed)

    if not isinstance(response.content, str):
        return str(response.content)
    return response.content
