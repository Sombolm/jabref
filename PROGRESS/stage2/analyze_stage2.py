"""Stage 2: Data Correlation & Hotspot Analysis for JabRef.

Performs:
- Task 2.1: Hotspot Identification (Complexity x Change Frequency)
- Task 2.2: Logical Coupling Analysis (>70% co-change + direct AST/import/reference check)
- Task 2.3: Knowledge Loss Risk (Bus Factor = 1 / high single-author share + author inactivity)

Outputs (saved in PROGRESS/stage2/):
- stage2_hotspots_top25.csv
- stage2_logical_coupling_gt70.csv
- stage2_knowledge_loss_risk.csv
- stage2_summary.json
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE1_DIR = REPO_ROOT / "PROGRESS" / "stage1"
STAGE2_DIR = Path(__file__).resolve().parent
BASELINE_COMMIT = "454ee663981cf6c51b5fc3f190fb0ed0fcdf799b"


def check_direct_dependency(path_a: str, path_b: str) -> dict[str, object]:
    """Check if two Java files have direct imports, same-package calls, or class-name references."""
    fa = REPO_ROOT / path_a
    fb = REPO_ROOT / path_b
    if not fa.exists() or not fb.exists():
        return {"has_direct_dep": None, "dep_reason": "file_missing"}

    text_a = fa.read_text(encoding="utf-8", errors="replace")
    text_b = fb.read_text(encoding="utf-8", errors="replace")

    cls_a = fa.stem
    cls_b = fb.stem

    pkg_a_m = re.search(r"^\s*package\s+([\w.]+)\s*;", text_a, re.M)
    pkg_b_m = re.search(r"^\s*package\s+([\w.]+)\s*;", text_b, re.M)
    pkg_a = pkg_a_m.group(1) if pkg_a_m else ""
    pkg_b = pkg_b_m.group(1) if pkg_b_m else ""

    fqn_a = f"{pkg_a}.{cls_a}" if pkg_a else cls_a
    fqn_b = f"{pkg_b}.{cls_b}" if pkg_b else cls_b

    a_imports_b = bool(re.search(rf"^\s*import\s+(?:static\s+)?{re.escape(fqn_b)}\b", text_a, re.M))
    b_imports_a = bool(re.search(rf"^\s*import\s+(?:static\s+)?{re.escape(fqn_a)}\b", text_b, re.M))

    # Strip package/import lines before checking symbol references in code body
    body_a = re.sub(r"^\s*(?:package|import)\s+.*;\s*$", "", text_a, flags=re.M)
    body_b = re.sub(r"^\s*(?:package|import)\s+.*;\s*$", "", text_b, flags=re.M)

    a_refs_b = bool(re.search(rf"\b{re.escape(cls_b)}\b", body_a))
    b_refs_a = bool(re.search(rf"\b{re.escape(cls_a)}\b", body_b))

    # Same package reference without explicit import
    same_pkg = (pkg_a == pkg_b) and pkg_a != ""

    reasons = []
    if a_imports_b:
        reasons.append(f"A imports {cls_b}")
    if b_imports_a:
        reasons.append(f"B imports {cls_a}")
    if same_pkg and a_refs_b:
        reasons.append(f"A references {cls_b} (same pkg)")
    elif a_refs_b and not a_imports_b:
        reasons.append(f"A mentions token {cls_b}")
    if same_pkg and b_refs_a:
        reasons.append(f"B references {cls_a} (same pkg)")
    elif b_refs_a and not b_imports_a:
        reasons.append(f"B mentions token {cls_a}")

    # Direct architectural dependency exists if imported or referenced in same package / qualified call
    has_direct = a_imports_b or b_imports_a or (same_pkg and (a_refs_b or b_refs_a)) or (
        f"{fqn_b}" in body_a or f"{fqn_a}" in body_b
    )
    return {
        "pkg_a": pkg_a,
        "pkg_b": pkg_b,
        "same_package": same_pkg,
        "a_imports_b": a_imports_b,
        "b_imports_a": b_imports_a,
        "a_refs_b": a_refs_b,
        "b_refs_a": b_refs_a,
        "has_direct_dep": has_direct,
        "dep_reason": "; ".join(reasons) if reasons else "none",
    }


def get_full_git_ownership(file_path: str) -> dict[str, object]:
    """Check full Git history ownership (all-time) for Bus Factor validation."""
    res = subprocess.run(
        ["git", "log", "--no-merges", "--format=%ae|%an|%aI", BASELINE_COMMIT, "--", file_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    if not lines:
        return {"all_time_commits": 0, "all_time_authors": 0, "all_time_top_author": "", "all_time_top_share": 0.0, "all_time_top_last_commit": ""}
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    last_dt: dict[str, str] = {}
    for ln in lines:
        parts = ln.split("|", 2)
        if len(parts) < 3:
            continue
        email, name, dt = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
        counts[email] = counts.get(email, 0) + 1
        if email not in names:
            names[email] = name
        if email not in last_dt or dt > last_dt[email]:
            last_dt[email] = dt
    top_email, top_cnt = max(counts.items(), key=lambda x: x[1])
    total = sum(counts.values())
    return {
        "all_time_commits": total,
        "all_time_authors": len(counts),
        "all_time_top_author": names[top_email],
        "all_time_top_email": top_email,
        "all_time_top_share": round(top_cnt / total, 4),
        "all_time_top_last_commit": last_dt[top_email],
    }


def main() -> None:
    STAGE2_DIR.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(STAGE1_DIR / "stage1_master_java_metrics.csv")
    coupling = pd.read_csv(STAGE1_DIR / "git_temporal_coupling_24m.csv")
    authors_24m = pd.read_csv(STAGE1_DIR / "git_author_activity_24m.csv")

    # ------------------------------------------------------------------
    # Task 2.1: Hotspot Identification (Complexity x Change Frequency)
    # Exclude module-info.java / package-info.java (0 complexity build manifests)
    # ------------------------------------------------------------------
    code_df = master[
        ~master["file_path"].str.endswith("module-info.java")
        & ~master["file_path"].str.endswith("package-info.java")
    ].copy()

    # Robust normalized scores (0..1 via log-scaling to avoid single-outlier distortion, plus raw product)
    code_df["norm_cog"] = np.log1p(code_df["pmd_cog_sum"]) / np.log1p(code_df["pmd_cog_sum"].max())
    code_df["norm_sloc"] = np.log1p(code_df["scc_sloc"]) / np.log1p(code_df["scc_sloc"].max())
    code_df["norm_cbo"] = np.log1p(code_df["ck_primary_cbo"].fillna(0)) / np.log1p(code_df["ck_primary_cbo"].fillna(0).max())
    code_df["norm_churn"] = np.log1p(code_df["commits_24m"]) / np.log1p(code_df["commits_24m"].max())

    # Composite Complexity Index = weighted Cognitive Complexity (50%), SLOC (30%), CBO (20%)
    code_df["complexity_index"] = 0.50 * code_df["norm_cog"] + 0.30 * code_df["norm_sloc"] + 0.20 * code_df["norm_cbo"]
    # Hotspot Score = geometric/multiplicative overlay of Complexity Index x Change Frequency
    code_df["hotspot_score"] = (code_df["complexity_index"] * code_df["norm_churn"] * 100.0).round(2)
    # Also compute direct Cog * Churn product for transparent comparison
    code_df["cog_x_commits24m"] = (code_df["pmd_cog_sum"] * code_df["commits_24m"]).astype(int)
    code_df["sloc_x_commits24m"] = (code_df["scc_sloc"] * code_df["commits_24m"]).astype(int)

    hotspots = code_df.sort_values("hotspot_score", ascending=False).head(25).copy()
    hotspot_cols = [
        "file_path",
        "module",
        "hotspot_score",
        "cog_x_commits24m",
        "sloc_x_commits24m",
        "commits_24m",
        "commits_12m",
        "total_churn_lines_24m",
        "scc_sloc",
        "pmd_cog_sum",
        "pmd_cog_max",
        "pmd_cyclo_class_total",
        "ck_primary_wmc",
        "ck_primary_cbo",
        "ck_primary_dit",
        "ck_primary_lcom_norm",
        "pmd_total_smells",
        "smell_GodClass",
        "distinct_authors_24m",
        "main_author_share",
    ]
    hotspots[hotspot_cols].to_csv(STAGE2_DIR / "stage2_hotspots_top25.csv", index=False)

    # ------------------------------------------------------------------
    # Task 2.2: Logical Coupling Analysis (>70% shared commits without direct dep)
    # ------------------------------------------------------------------
    main_coupling = coupling[
        coupling["file_a"].str.contains("/src/main/java/", regex=False)
        & coupling["file_b"].str.contains("/src/main/java/", regex=False)
        & (coupling["max_confidence"] > 0.70)
    ].copy()

    # Also ignore module-info.java manifest pairs in primary code-level report (track flag)
    dep_checks = []
    for row in main_coupling.itertuples(index=False):
        info = check_direct_dependency(row.file_a, row.file_b)
        info["is_module_info"] = row.file_a.endswith("module-info.java") or row.file_b.endswith("module-info.java")
        dep_checks.append(info)

    dep_df = pd.DataFrame(dep_checks)
    coupled_enriched = pd.concat([main_coupling.reset_index(drop=True), dep_df], axis=1)
    coupled_enriched = coupled_enriched.sort_values(
        ["has_direct_dep", "is_module_info", "shared_commits", "max_confidence"],
        ascending=[True, True, False, False],
    )
    coupled_enriched.to_csv(STAGE2_DIR / "stage2_logical_coupling_gt70.csv", index=False)

    # ------------------------------------------------------------------
    # Task 2.3: Knowledge Loss Risk (Bus Factor = 1 on complex core components)
    # Check 24m Bus Factor = 1 (or main_author_share >= 0.85) on complex files,
    # and verify full-history Git ownership + author inactivity!
    # ------------------------------------------------------------------
    author_last_map = dict(zip(authors_24m["author_email"], authors_24m["last_commit_24m"]))
    author_active_map = dict(zip(authors_24m["author_email"], authors_24m["active_last_6m"]))

    kl_candidates = code_df[
        (code_df["scc_sloc"] >= 150)
        & ((code_df["pmd_cog_sum"] >= 15) | (code_df["ck_primary_wmc"].fillna(0) >= 20) | (code_df["ck_primary_cbo"].fillna(0) >= 15))
        & ((code_df["distinct_authors_24m"] == 1) | (code_df["main_author_share"] >= 0.80))
    ].copy()

    kl_candidates["risk_score"] = (
        kl_candidates["complexity_index"]
        * kl_candidates["main_author_share"]
        * np.where(kl_candidates["main_author_active_6m"] == False, 1.5, 1.0)
        * 100.0
    ).round(2)
    kl_candidates = kl_candidates.sort_values(["main_author_active_6m", "risk_score"], ascending=[True, False])

    # Validate top 40 candidates against ALL-TIME git history
    top_kl = kl_candidates.head(40).copy()
    all_time_records = [get_full_git_ownership(fp) for fp in top_kl["file_path"]]
    at_df = pd.DataFrame(all_time_records)
    top_kl = pd.concat([top_kl.reset_index(drop=True), at_df], axis=1)
    # Check if all-time top author is active in last 6m (from 24m author table)
    top_kl["all_time_top_active_6m"] = top_kl["all_time_top_email"].map(lambda e: bool(author_active_map.get(e, False)))

    kl_cols = [
        "file_path",
        "module",
        "risk_score",
        "scc_sloc",
        "pmd_cog_sum",
        "pmd_cog_max",
        "ck_primary_wmc",
        "ck_primary_cbo",
        "pmd_total_smells",
        "commits_24m",
        "distinct_authors_24m",
        "main_author_name",
        "main_author_share",
        "main_author_active_6m",
        "all_time_commits",
        "all_time_authors",
        "all_time_top_author",
        "all_time_top_share",
        "all_time_top_active_6m",
        "all_time_top_last_commit",
    ]
    top_kl[kl_cols].to_csv(STAGE2_DIR / "stage2_knowledge_loss_risk.csv", index=False)

    # Save summary JSON
    summary = {
        "top5_hotspots": hotspots[hotspot_cols].head(5).to_dict(orient="records"),
        "logical_coupling_gt70_total": int(len(coupled_enriched)),
        "logical_coupling_gt70_no_direct_dep_non_manifest": int(
            len(coupled_enriched[(coupled_enriched["has_direct_dep"] == False) & (coupled_enriched["is_module_info"] == False)])
        ),
        "logical_coupling_no_direct_dep_top10": coupled_enriched[
            (coupled_enriched["has_direct_dep"] == False) & (coupled_enriched["is_module_info"] == False)
        ].head(10).to_dict(orient="records"),
        "knowledge_loss_candidates_total": int(len(kl_candidates)),
        "knowledge_loss_inactive_owner_count": int((kl_candidates["main_author_active_6m"] == False).sum()),
        "knowledge_loss_all_time_bf1_top10": top_kl[
            (top_kl["all_time_authors"] == 1) | (top_kl["all_time_top_share"] >= 0.85)
        ].head(10)[kl_cols].to_dict(orient="records"),
    }
    with (STAGE2_DIR / "stage2_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=== TASK 2.1: TOP 10 HOTSPOTS (Complexity x Churn) ===")
    print(hotspots[["file_path", "hotspot_score", "commits_24m", "commits_12m", "scc_sloc", "pmd_cog_sum", "ck_primary_cbo", "pmd_total_smells"]].head(10).to_string(index=False))

    print("\n=== TASK 2.2: LOGICAL COUPLING >70% WITHOUT DIRECT ARCHITECTURAL DEPENDENCY ===")
    no_dep = coupled_enriched[(coupled_enriched["has_direct_dep"] == False) & (coupled_enriched["is_module_info"] == False)]
    print(f"Found {len(no_dep)} non-manifest pairs >70% co-change without direct dependency (out of {len(coupled_enriched)} >70% pairs):")
    print(no_dep[["file_a", "file_b", "shared_commits", "commits_a", "commits_b", "confidence_a_to_b", "confidence_b_to_a", "dep_reason"]].head(15).to_string(index=False))

    print("\n=== TASK 2.3: KNOWLEDGE LOSS RISK (Inactive or All-Time Bus Factor = 1) ===")
    print(top_kl[["file_path", "scc_sloc", "pmd_cog_sum", "commits_24m", "main_author_name", "main_author_active_6m", "all_time_authors", "all_time_top_share", "all_time_top_active_6m"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
