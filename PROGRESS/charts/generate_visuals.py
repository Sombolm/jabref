"""Generate publication-quality PNG charts and combined PDF for JabRef Maintainability Audit.

Outputs (saved in PROGRESS/charts/):
- 01_hotspot_matrix.png
- 02_code_smell_distribution.png
- 03_logical_coupling_and_bus_factor.png
- 04_module_health_overview.png
- jabref_audit_charts.pdf
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE1_DIR = REPO_ROOT / "PROGRESS" / "stage1"
STAGE2_DIR = REPO_ROOT / "PROGRESS" / "stage2"
CHARTS_DIR = Path(__file__).resolve().parent

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Segoe UI"]


def short_name(path: str) -> str:
    return Path(path).stem


def make_hotspot_matrix(master: pd.DataFrame, hotspots: pd.DataFrame) -> plt.Figure:
    df = master[
        ~master["file_path"].str.endswith("module-info.java")
        & ~master["file_path"].str.endswith("package-info.java")
    ].copy()
    df["cbo_clean"] = df["ck_primary_cbo"].fillna(0).clip(upper=110)

    fig, ax = plt.subplots(figsize=(12, 7.5))
    sc = ax.scatter(
        df["commits_24m"],
        df["pmd_cog_sum"],
        s=(df["scc_sloc"].clip(lower=20) / 10.0) + 12,
        c=df["cbo_clean"],
        cmap="YlOrRd",
        alpha=0.68,
        edgecolors="#222222",
        linewidths=0.4,
    )
    cbar = plt.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("CK Coupling Between Objects (CBO)", fontsize=10)

    # Quadrant reference lines (90th percentiles)
    x_q90 = float(df["commits_24m"].quantile(0.95))
    y_q90 = float(df["pmd_cog_sum"].quantile(0.95))
    ax.axvline(x_q90, color="#555555", linestyle="--", linewidth=1.1, alpha=0.7)
    ax.axhline(y_q90, color="#555555", linestyle="--", linewidth=1.1, alpha=0.7)

    # Quadrant labels
    ax.text(
        0.98,
        0.96,
        f"CRITICAL HOTSPOTS\n(Churn >= {x_q90:.0f} & Cog >= {y_q90:.0f})",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color="#990000",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#fff0f0", edgecolor="#cc0000", alpha=0.9),
    )
    ax.text(
        0.02,
        0.86,
        "HIGH COMPLEXITY / LOW CHURN\n(Latent Technical Debt)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#444444",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#f7f7f7", edgecolor="#aaaaaa", alpha=0.85),
    )

    # Annotate Top 5 Hotspots + key runner-up + top complexity outliers
    top5_paths = hotspots["file_path"].head(5).tolist()
    offsets = {
        "JabRefCliPreferences": (-165, 22),
        "LibraryTab": (-40, 48),
        "JabRefGuiPreferences": (24, -36),
        "JabRefFrame": (32, 24),
        "CitationRelationsTab": (-155, -36),
        "ImportHandler": (-25, 16),
        "MedlineImporter": (14, -4),
        "BracketedPattern": (12, 4),
        "RisImporter": (12, 4),
        "BibtexParser": (12, -10),
    }

    for rank, path in enumerate(top5_paths, start=1):
        row = df[df["file_path"] == path].iloc[0]
        name = short_name(path)
        dx, dy = offsets.get(name, (8, 8))
        ax.scatter(
            [row["commits_24m"]],
            [row["pmd_cog_sum"]],
            s=(row["scc_sloc"] / 10.0) + 45,
            facecolors="none",
            edgecolors="#0033cc",
            linewidths=2.0,
            zorder=5,
        )
        ax.annotate(
            f"#{rank} {name}\n({int(row['commits_24m'])}c, Cog {int(row['pmd_cog_sum'])}, {int(row['scc_sloc'])} SLOC)",
            xy=(row["commits_24m"], row["pmd_cog_sum"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8.5,
            fontweight="bold",
            color="#002288",
            arrowprops=dict(arrowstyle="->", color="#0033cc", lw=1.0),
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#0033cc", alpha=0.9),
            zorder=6,
        )

    # Annotate notable high-complexity outliers & ImportHandler
    for extra in [
        "jabgui/src/main/java/org/jabref/gui/externalfiles/ImportHandler.java",
        "jablib/src/main/java/org/jabref/logic/importer/fileformat/MedlineImporter.java",
        "jablib/src/main/java/org/jabref/logic/citationkeypattern/BracketedPattern.java",
        "jablib/src/main/java/org/jabref/logic/importer/fileformat/RisImporter.java",
        "jablib/src/main/java/org/jabref/logic/importer/fileformat/BibtexParser.java",
    ]:
        sub = df[df["file_path"] == extra]
        if sub.empty:
            continue
        row = sub.iloc[0]
        name = short_name(extra)
        dx, dy = offsets.get(name, (8, 6))
        ax.annotate(
            f"{name} ({int(row['commits_24m'])}c, Cog {int(row['pmd_cog_sum'])})",
            xy=(row["commits_24m"], row["pmd_cog_sum"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8,
            color="#333333",
            arrowprops=dict(arrowstyle="->", color="#666666", lw=0.8),
        )

    ax.set_title(
        "JabRef Hotspot Matrix: Cognitive Complexity vs. 24-Month Change Frequency\n"
        "(2,298 Production Java Files | Bubble Size = SLOC, Color = CBO)",
        fontsize=12.5,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("24-Month Change Frequency (Commits Modifying File)", fontsize=11)
    ax.set_ylabel("Total Cognitive Complexity (PMD Method Sum)", fontsize=11)
    ax.set_xlim(-3, df["commits_24m"].max() + 14)
    ax.set_ylim(-15, df["pmd_cog_sum"].max() + 45)
    fig.tight_layout()
    return fig


def make_code_smells_chart(smells_raw: pd.DataFrame) -> plt.Figure:
    smells = smells_raw.copy()
    smells["file_path"] = smells["File"].astype(str).str.replace("\\", "/")
    smells["module"] = smells["file_path"].str.extract(r"^(?:.*/)?(jab[a-z-]+)/src/")[0].fillna("other")
    smells["module_grp"] = smells["module"].where(smells["module"].isin(["jablib", "jabgui"]), "other (jabkit/jabls/jabsrv)")

    rule_counts = smells["Rule"].value_counts()
    pivot = pd.crosstab(smells["Rule"], smells["module_grp"]).loc[rule_counts.index[::-1]]
    cols_order = [c for c in ["jablib", "jabgui", "other (jabkit/jabls/jabsrv)"] if c in pivot.columns]
    pivot = pivot[cols_order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={"width_ratios": [1.5, 1.0]})

    pivot.plot(
        kind="barh",
        stacked=True,
        ax=ax1,
        color=["#2b5c8f", "#e07b39", "#6ba368"][: len(cols_order)],
        edgecolor="white",
        linewidth=0.5,
    )
    for i, total in enumerate(pivot.sum(axis=1)):
        ax1.text(total + 12, i, f"{int(total)}", va="center", fontsize=8.5, fontweight="bold")
    ax1.set_title("PMD Code Smells by Rule & Module (Total = 3,007)", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("Violation Count", fontsize=10)
    ax1.set_ylabel("")
    ax1.set_xlim(0, pivot.sum(axis=1).max() * 1.15)
    ax1.legend(title="Module", loc="lower right")

    # Right panel: Top 12 smell-densest files
    top_files = smells.groupby("file_path")["Rule"].count().sort_values(ascending=False).head(12)
    labels = [f"{short_name(p)} ({p.split('/')[-2] if '/' in p else ''})" for p in top_files.index][::-1]
    # Better labels with module prefix
    labels = []
    for p in top_files.index[::-1]:
        mod = "jablib" if p.startswith("jablib/") or "/jablib/" in p else ("jabgui" if p.startswith("jabgui/") or "/jabgui/" in p else "other")
        labels.append(f"[{mod}] {short_name(p)}")
    vals = top_files.values[::-1]
    bars = ax2.barh(labels, vals, color="#b03a2e", alpha=0.88)
    for bar, v in zip(bars, vals):
        ax2.text(v + 1.5, bar.get_y() + bar.get_height() / 2, f"{int(v)}", va="center", fontsize=8.5, fontweight="bold")
    ax2.set_title("Top 12 Files by Total PMD Smell Count", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Total Smells in File", fontsize=10)
    ax2.set_xlim(0, max(vals) * 1.15)

    fig.suptitle("JabRef Code Smells Distribution (Production Java Sources)", fontsize=13, fontweight="bold", y=0.99)
    fig.tight_layout()
    return fig


def make_coupling_and_bus_factor_chart(coupling: pd.DataFrame, kl_df: pd.DataFrame, master: pd.DataFrame) -> plt.Figure:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6.8))

    # Left: Logical Coupling (>70% without direct architectural dependency)
    no_dep = coupling[(coupling["has_direct_dep"] == False) & (coupling["is_module_info"] == False)].copy()
    no_dep = no_dep.sort_values(["shared_commits", "max_confidence"], ascending=[True, True]).tail(11)
    pair_labels = [f"{short_name(r.file_a)} <-> {short_name(r.file_b)}" for r in no_dep.itertuples()]

    y_pos = np.arange(len(pair_labels))
    h = 0.36
    ax1.barh(y_pos + h / 2, no_dep["confidence_a_to_b"] * 100, height=h, label="Conf(A -> B) %", color="#3b7dd8")
    ax1.barh(y_pos - h / 2, no_dep["confidence_b_to_a"] * 100, height=h, label="Conf(B -> A) %", color="#f39c12")
    ax1.axvline(70, color="#c0392b", linestyle="--", linewidth=1.2, label="70% Threshold")

    for i, r in enumerate(no_dep.itertuples()):
        mx = max(r.confidence_a_to_b, r.confidence_b_to_a) * 100
        ax1.text(mx + 1.5, i, f"{r.shared_commits} shared", va="center", fontsize=8, fontweight="bold")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(pair_labels, fontsize=8.5)
    ax1.set_xlim(0, 112)
    ax1.set_xlabel("Co-Change Confidence (%)", fontsize=10)
    ax1.set_title("Logical Coupling >70% Without Direct Dependency\n(11 Non-Manifest Production Pairs)", fontsize=11, fontweight="bold")
    ax1.legend(loc="lower right", fontsize=8.5)

    # Right: Knowledge Loss Risk (Main Author Share vs Cognitive Complexity for SLOC >= 100)
    m = master[
        ~master["file_path"].str.endswith("module-info.java")
        & ~master["file_path"].str.endswith("package-info.java")
        & (master["scc_sloc"] >= 100)
    ].copy()
    active_m = m[m["main_author_active_6m"] == True]
    inactive_m = m[m["main_author_active_6m"] == False]

    ax2.scatter(
        active_m["main_author_share"] * 100,
        active_m["pmd_cog_sum"],
        s=active_m["scc_sloc"] / 8.0 + 10,
        alpha=0.45,
        color="#4a90d9",
        label="Main Author Active (<6m)",
    )
    ax2.scatter(
        inactive_m["main_author_share"] * 100,
        inactive_m["pmd_cog_sum"],
        s=inactive_m["scc_sloc"] / 6.0 + 35,
        alpha=0.88,
        color="#d9381e",
        edgecolors="black",
        linewidths=0.7,
        label="Main Author Inactive (>6m)",
        zorder=5,
    )
    ax2.axvline(80, color="#7f8c8d", linestyle="--", linewidth=1.1)
    ax2.text(81, m["pmd_cog_sum"].max() * 0.92, "High Concentration\n(>=80% 1 Author)", fontsize=8.5, color="#555555")

    # Annotate notable BF=1 / inactive risk files with clean non-overlapping positions
    highlight_offsets = {
        "Authors.java": (-18, 8),
        "DBMSConnectionUrl.java": (-22, 12),
        "BibframeImporter.java": (-95, 38),
        "CitationEntryReviewDialog.java": (-110, 12),
        "DefinitionProvider.java": (-20, 26),
        "PanelStep.java": (-20, -4),
        "TooltipStep.java": (-20, -24),
        "WalkthroughAction.java": (12, 24),
    }
    for r in m[m["file_path"].apply(lambda p: Path(p).name in highlight_offsets)].itertuples():
        fname = Path(r.file_path).name
        dx, dy = highlight_offsets[fname]
        lbl = f"{short_name(r.file_path)} ({int(r.main_author_share*100)}%)"
        ax2.annotate(
            lbl,
            xy=(r.main_author_share * 100, r.pmd_cog_sum),
            xytext=(dx, dy),
            textcoords="offset points",
            ha="right" if dx < 0 else "left",
            fontsize=7.8,
            arrowprops=dict(arrowstyle="->", lw=0.7, color="#444444"),
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="#cccccc", alpha=0.85),
        )

    ax2.set_title("Knowledge Loss Risk (SLOC >= 100): Ownership vs. Complexity\n(Bus Factor = 1 & Inactive Maintainers Highlighted)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Main Author Commit Share (%, 24m)", fontsize=10)
    ax2.set_ylabel("Cognitive Complexity (File Sum)", fontsize=10)
    ax2.set_xlim(10, 108)
    ax2.legend(loc="upper left", fontsize=8.5)

    fig.tight_layout()
    return fig


def make_module_health_chart(master: pd.DataFrame) -> plt.Figure:
    df = master[
        master["module"].isin(["jablib", "jabgui", "jabsrv", "jabkit", "jabls"])
        & ~master["file_path"].str.endswith("module-info.java")
        & ~master["file_path"].str.endswith("package-info.java")
    ].copy()

    grp = (
        df.groupby("module", as_index=False)
        .agg(
            files=("file_path", "count"),
            sloc=("scc_sloc", "sum"),
            smells=("pmd_total_smells", "sum"),
            god_classes=("smell_GodClass", "sum"),
            mean_cbo=("ck_primary_cbo", "mean"),
            mean_cog=("pmd_cog_sum", "mean"),
            total_commits=("commits_24m", "sum"),
        )
        .sort_values("sloc", ascending=False)
    )
    grp["smells_per_1k_sloc"] = (grp["smells"] / grp["sloc"]) * 1000.0

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    palette = ["#2b5c8f", "#e07b39", "#5c9e58", "#8e44ad", "#16a085"]

    axes[0].bar(grp["module"], grp["sloc"], color=palette)
    for i, v in enumerate(grp["sloc"]):
        axes[0].text(i, v + 2000, f"{int(v):,}", ha="center", fontsize=8.5, fontweight="bold")
    axes[0].set_title("Production SLOC by Module", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("SLOC")
    axes[0].set_ylim(0, grp["sloc"].max() * 1.15)

    axes[1].bar(grp["module"], grp["smells_per_1k_sloc"], color=palette)
    for i, (v, gc) in enumerate(zip(grp["smells_per_1k_sloc"], grp["god_classes"])):
        axes[1].text(i, v + 0.4, f"{v:.1f}\n({int(gc)} God)", ha="center", fontsize=8, fontweight="bold")
    axes[1].set_title("Smell Density (per 1k SLOC) & God Classes", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("PMD Smells / 1,000 SLOC")
    axes[1].set_ylim(0, grp["smells_per_1k_sloc"].max() * 1.25)

    axes[2].bar(grp["module"], grp["mean_cbo"], color=palette)
    for i, v in enumerate(grp["mean_cbo"]):
        axes[2].text(i, v + 0.3, f"{v:.2f}", ha="center", fontsize=8.5, fontweight="bold")
    axes[2].set_title("Mean Coupling Between Objects (CBO)", fontsize=11, fontweight="bold")
    axes[2].set_ylabel("Mean CK CBO")
    axes[2].set_ylim(0, grp["mean_cbo"].max() * 1.2)

    fig.suptitle("JabRef Module-Level Maintainability Comparison (Production Java)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(STAGE1_DIR / "stage1_master_java_metrics.csv")
    smells_raw = pd.read_csv(STAGE1_DIR / "pmd_smells_main.csv")
    hotspots = pd.read_csv(STAGE2_DIR / "stage2_hotspots_top25.csv")
    coupling = pd.read_csv(STAGE2_DIR / "stage2_logical_coupling_gt70.csv")
    kl_df = pd.read_csv(STAGE2_DIR / "stage2_knowledge_loss_risk.csv")

    figs = [
        ("01_hotspot_matrix.png", make_hotspot_matrix(master, hotspots)),
        ("02_code_smell_distribution.png", make_code_smells_chart(smells_raw)),
        ("03_logical_coupling_and_bus_factor.png", make_coupling_and_bus_factor_chart(coupling, kl_df, master)),
        ("04_module_health_overview.png", make_module_health_chart(master)),
    ]

    pdf_path = CHARTS_DIR / "jabref_audit_charts.pdf"
    with PdfPages(pdf_path) as pdf:
        for fname, fig in figs:
            out_png = CHARTS_DIR / fname
            fig.savefig(out_png, bbox_inches="tight")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            print(f"Saved {out_png}")

    print(f"Saved combined PDF: {pdf_path}")


if __name__ == "__main__":
    main()
