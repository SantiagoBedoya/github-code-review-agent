"""Generate bandit learning visualizations from snapshot data.

Usage:
    uv run python scripts/visualize_bandit.py
    uv run python scripts/visualize_bandit.py --output-dir ./plots
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_code_review.database import BanditSnapshot, get_session

AGENT_NAMES = ["seguridad", "estructuras", "calidad", "performance", "documentacion"]
AGENT_LABELS = {
    "seguridad": "Seguridad",
    "estructuras": "Estructuras",
    "calidad": "Calidad",
    "performance": "Performance",
    "documentacion": "Documentación",
}
AGENT_COLORS = {
    "seguridad": "#e74c3c",
    "estructuras": "#3498db",
    "calidad": "#2ecc71",
    "performance": "#f39c12",
    "documentacion": "#9b59b6",
}
EXTENSION_LABELS = [
    ".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".cs", "other",
]


async def fetch_snapshots():
    session = await get_session()
    async with session:
        rows = await session.stream(
            select(BanditSnapshot).order_by(BanditSnapshot.id)
        )
        snapshots = [row[0] async for row in rows]
    return snapshots


def plot_weight_evolution(snapshots, output_dir: Path):
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    axes = axes.flatten()
    fig.suptitle("Evolución de Pesos por Agente (Contextual Bandit)", fontsize=14)

    for idx, agent in enumerate(AGENT_NAMES):
        ax = axes[idx]
        agent_snaps = [s for s in snapshots if s.agent_name == agent and s.ran]
        if not agent_snaps:
            ax.set_title(f"{AGENT_LABELS[agent]} — sin datos")
            continue

        steps = [s.step for s in agent_snaps]
        for wi in range(9):
            vals = [s.weights[wi] for s in agent_snaps]
            label = EXTENSION_LABELS[wi] if wi < 9 else f"w{wi}"
            ax.plot(steps, vals, label=label, linewidth=1.2)

        ax.set_title(AGENT_LABELS[agent])
        ax.set_xlabel("Paso (count)")
        ax.set_ylabel("Peso")
        ax.legend(fontsize=7, ncol=3)
        ax.grid(True, alpha=0.3)

    axes[-1].axis("off")
    plt.tight_layout()
    path = output_dir / "weight_evolution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  → {path}")


def plot_epsilon_decay(snapshots, output_dir: Path):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.suptitle("Decaimiento de ε (Exploración vs Explotación)", fontsize=14)

    uniq: dict[int, float] = {}
    for s in snapshots:
        uniq[s.step] = s.epsilon
    sorted_steps = sorted(uniq.keys())
    epsilons = [uniq[s] for s in sorted_steps]

    ax.plot(sorted_steps, epsilons, marker=".", linestyle="-", color="#2c3e50")
    ax.set_xlabel("Paso (count)")
    ax.set_ylabel("ε (epsilon)")
    ax.set_ylim(-0.02, 0.52)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))

    plt.tight_layout()
    path = output_dir / "epsilon_decay.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  → {path}")


def plot_cumulative_reward(snapshots, output_dir: Path):
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("Recompensa Acumulada por Agente", fontsize=14)

    for agent in AGENT_NAMES:
        agent_snaps = [s for s in snapshots if s.agent_name == agent and s.ran and s.reward is not None]
        if not agent_snaps:
            continue
        steps = [s.step for s in agent_snaps]
        cum_reward = [sum(s.reward for s in agent_snaps[:i+1]) for i in range(len(agent_snaps))]
        ax.plot(steps, cum_reward, label=AGENT_LABELS[agent], color=AGENT_COLORS[agent], linewidth=1.5)

    ax.set_xlabel("Paso (count)")
    ax.set_ylabel("Recompensa acumulada")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = output_dir / "cumulative_reward.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  → {path}")


def plot_decision_matrix(snapshots, output_dir: Path):
    ext_order = [".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".cs"]
    agent_order = AGENT_NAMES

    run_count: dict[tuple[str, str], int] = {}
    total_count: dict[tuple[str, str], int] = {}
    for ext in ext_order:
        for agent in agent_order:
            run_count[(ext, agent)] = 0
            total_count[(ext, agent)] = 0

    for s in snapshots:
        ext = s.file_ext
        if ext not in ext_order:
            ext = "other"
        if ext not in ext_order:
            continue
        total_count[(ext, s.agent_name)] = total_count.get((ext, s.agent_name), 0) + 1
        if s.ran:
            run_count[(ext, s.agent_name)] = run_count.get((ext, s.agent_name), 0) + 1

    ratios = []
    for ext in ext_order:
        row = []
        for agent in agent_order:
            t = total_count.get((ext, agent), 0)
            r = run_count.get((ext, agent), 0)
            row.append(r / t if t > 0 else 0)
        ratios.append(row)

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle("Tasa de Ejecución por Extensión y Agente", fontsize=14)

    im = ax.imshow(ratios, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(agent_order)))
    ax.set_xticklabels([AGENT_LABELS[a] for a in agent_order], rotation=30, ha="right")
    ax.set_yticks(range(len(ext_order)))
    ax.set_yticklabels(ext_order)

    for i in range(len(ext_order)):
        for j in range(len(agent_order)):
            val = ratios[i][j]
            color = "white" if val < 0.5 else "black"
            ax.text(j, i, f"{val:.0%}", ha="center", va="center", fontsize=9, color=color)

    fig.colorbar(im, ax=ax, label="Tasa de ejecución")
    plt.tight_layout()
    path = output_dir / "decision_matrix.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  → {path}")


async def main():
    parser = argparse.ArgumentParser(description="Genera visualizaciones del bandit contextual")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./plots",
        help="Directorio de salida para los gráficos (default: ./plots)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Obteniendo snapshots de la base de datos…")
    snapshots = await fetch_snapshots()
    print(f"  → {len(snapshots)} snapshots encontrados")

    if not snapshots:
        print("  ⚠️  No hay datos. Ejecuta algunas revisiones primero.")
        return

    print("Generando visualizaciones…")
    plot_weight_evolution(snapshots, output_dir)
    plot_epsilon_decay(snapshots, output_dir)
    plot_cumulative_reward(snapshots, output_dir)
    plot_decision_matrix(snapshots, output_dir)

    print(f"\n✅ Gráficos guardados en: {output_dir.resolve()}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
