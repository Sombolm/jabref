"""Consolidate Stage 1 raw tool outputs into clean normalized CSVs and summary JSON.

Inputs:
- .audit-tools/ck-{jablib,gui-max1,jabkit,jabls,jabsrv,jabls-cli,jabsrv-cli}/{class,method}.csv
- PROGRESS/stage1/scc_java_files.csv
- PROGRESS/stage1/pmd_complexity_main.csv
- PROGRESS/stage1/pmd_smells_main.csv
- PROGRESS/stage1/pmd_cpd_main.csv
- PROGRESS/stage1/git_file_evolution_24m.csv

Outputs (saved in PROGRESS/stage1/):
- ck_class_metrics.csv
- ck_file_metrics.csv
- pmd_file_complexity.csv
- pmd_file_smells.csv
- stage1_master_java_metrics.csv
- stage1_summary_stats.json
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE1_DIR = Path(__file__).resolve().parent
TOOLS_DIR = REPO_ROOT / ".audit-tools"

CK_MODULES = [
    ("jablib", "ck-jablib"),
    ("jabgui", "ck-gui-max1"),
    ("jabkit", "ck-jabkit"),
    ("jabls", "ck-jabls"),
    ("jabsrv", "ck-jabsrv"),
    ("jabls-cli", "ck-jabls-cli"),
    ("jabsrv-cli", "ck-jabsrv-cli"),
]

CYCLO_CLASS_RE = re.compile(r"has a total cyclomatic complexity of (\d+) \(highest (\d+)\)")
CYCLO_METHOD_RE = re.compile(r"has a(?: standard)? cyclomatic complexity of (\d+)")
COG_METHOD_RE = re.compile(r"has a cognitive complexity of (\d+)")


def normalize_repo_path(raw: str) -> str:
    s = raw.replace("\\", "/")
    # Strip Windows prefix ending with module root or repo root
    for marker in ("/jablib/", "/jabgui/", "/jabkit/", "/jabls/", "/jabls-cli/", "/jabsrv/", "/jabsrv-cli/", "/jablib-examples/", "/test-support/"):
        idx = s.find(marker)
        if idx != -1:
            return s[idx + 1 :]
    for prefix in ("jablib/", "jabgui/", "jabkit/", "jabls/", "jabls-cli/", "jabsrv/", "jabsrv-cli/", "jablib-examples/", "test-support/"):
        if s.startswith(prefix):
            return s
    return s


def build_ck() -> tuple[pd.DataFrame, pd.DataFrame]:
    class_frames = []
    for mod_name, folder_name in CK_MODULES:
        p = TOOLS_DIR / folder_name / "class.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace")
        df["module"] = mod_name
        df["file_path"] = df["file"].astype(str).map(normalize_repo_path)
        class_frames.append(df)

    ck_classes = pd.concat(class_frames, ignore_index=True)
    ck_classes.to_csv(STAGE1_DIR / "ck_class_metrics.csv", index=False)

    # Aggregate to file level: keep primary top-level class stats + max/sum where appropriate
    # Primary class = shortest class name (not anonymous/inner '$') or highest LOC
    ck_classes["is_inner"] = ck_classes["class"].astype(str).str.contains(r"\$", regex=True)
    ck_sorted = ck_classes.sort_values(["file_path", "is_inner", "loc"], ascending=[True, True, False])
    primary = ck_sorted.drop_duplicates(subset=["file_path"], keep="first").copy()

    agg = (
        ck_classes.groupby("file_path", as_index=False)
        .agg(
            ck_classes_in_file=("class", "count"),
            ck_wmc_sum=("wmc", "sum"),
            ck_wmc_max=("wmc", "max"),
            ck_dit_max=("dit", "max"),
            ck_cbo_max=("cbo", "max"),
            ck_cbo_modified_max=("cboModified", "max"),
            ck_fanin_max=("fanin", "max"),
            ck_fanout_max=("fanout", "max"),
            ck_rfc_max=("rfc", "max"),
            ck_lcom_norm_max=("lcom*", "max"),
            ck_loc_primary=("loc", "max"),
            ck_methods_sum=("totalMethodsQty", "sum"),
            ck_fields_sum=("totalFieldsQty", "sum"),
            ck_max_nested_blocks=("maxNestedBlocksQty", "max"),
        )
    )
    ck_file = agg.merge(
        primary[["file_path", "module", "class", "cbo", "wmc", "dit", "rfc", "lcom*", "tcc", "lcc", "loc"]].rename(
            columns={
                "class": "primary_class",
                "cbo": "ck_primary_cbo",
                "wmc": "ck_primary_wmc",
                "dit": "ck_primary_dit",
                "rfc": "ck_primary_rfc",
                "lcom*": "ck_primary_lcom_norm",
                "tcc": "ck_primary_tcc",
                "lcc": "ck_primary_lcc",
                "loc": "ck_primary_loc",
            }
        ),
        on="file_path",
        how="left",
    )
    ck_file.to_csv(STAGE1_DIR / "ck_file_metrics.csv", index=False)
    return ck_classes, ck_file


def build_pmd_complexity() -> pd.DataFrame:
    df = pd.read_csv(STAGE1_DIR / "pmd_complexity_main.csv", encoding="utf-8", encoding_errors="replace")
    df["file_path"] = df["File"].astype(str).map(normalize_repo_path)

    per_file: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "pmd_cyclo_class_total": 0,
            "pmd_cyclo_class_highest_method": 0,
            "pmd_cyclo_method_sum": 0,
            "pmd_cyclo_method_max": 0,
            "pmd_cyclo_method_count": 0,
            "pmd_cog_sum": 0,
            "pmd_cog_max": 0,
            "pmd_cog_method_count": 0,
            "pmd_cog_methods_ge_15": 0,
        }
    )

    for row in df.itertuples(index=False):
        fp = row.file_path
        rule = row.Rule
        desc = str(row.Description)
        rec = per_file[fp]

        if rule == "CyclomaticComplexity":
            m_cls = CYCLO_CLASS_RE.search(desc)
            if m_cls:
                total_c = int(m_cls.group(1))
                high_c = int(m_cls.group(2))
                rec["pmd_cyclo_class_total"] += total_c
                rec["pmd_cyclo_class_highest_method"] = max(rec["pmd_cyclo_class_highest_method"], high_c)
            else:
                m_meth = CYCLO_METHOD_RE.search(desc)
                if m_meth:
                    val = int(m_meth.group(1))
                    rec["pmd_cyclo_method_sum"] += val
                    rec["pmd_cyclo_method_max"] = max(rec["pmd_cyclo_method_max"], val)
                    rec["pmd_cyclo_method_count"] += 1
        elif rule == "CognitiveComplexity":
            m_cog = COG_METHOD_RE.search(desc)
            if m_cog:
                val = int(m_cog.group(1))
                rec["pmd_cog_sum"] += val
                rec["pmd_cog_max"] = max(rec["pmd_cog_max"], val)
                rec["pmd_cog_method_count"] += 1
                if val >= 15:
                    rec["pmd_cog_methods_ge_15"] += 1

    out = pd.DataFrame([{"file_path": k, **v} for k, v in per_file.items()])
    out.to_csv(STAGE1_DIR / "pmd_file_complexity.csv", index=False)
    return out


def build_pmd_smells() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(STAGE1_DIR / "pmd_smells_main.csv", encoding="utf-8", encoding_errors="replace")
    df["file_path"] = df["File"].astype(str).map(normalize_repo_path)

    piv = pd.crosstab(df["file_path"], df["Rule"]).reset_index()
    rule_cols = [c for c in piv.columns if c != "file_path"]
    piv["pmd_total_smells"] = piv[rule_cols].sum(axis=1)
    rename_map = {c: f"smell_{c}" for c in rule_cols}
    piv = piv.rename(columns=rename_map)
    piv.to_csv(STAGE1_DIR / "pmd_file_smells.csv", index=False)
    return df, piv


def build_cpd_summary() -> tuple[dict, pd.DataFrame]:
    cpd_path = STAGE1_DIR / "pmd_cpd_main.csv"
    file_dup_lines: Counter[str] = Counter()
    file_dup_clones: Counter[str] = Counter()
    clone_groups = []

    with cpd_path.open("r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            lines = int(row[0])
            tokens = int(row[1])
            occ = int(row[2])
            files_in_clone = []
            # pairs of (start_line, path) follow after index 2
            idx = 3
            while idx + 1 < len(row):
                start_line = int(row[idx])
                fpath = normalize_repo_path(row[idx + 1])
                files_in_clone.append((start_line, fpath))
                file_dup_lines[fpath] += lines
                file_dup_clones[fpath] += 1
                idx += 2
            clone_groups.append(
                {
                    "lines": lines,
                    "tokens": tokens,
                    "occurrences": occ,
                    "files": [p for _, p in files_in_clone],
                }
            )

    cpd_df = pd.DataFrame(
        [
            {"file_path": k, "cpd_duplicated_lines": file_dup_lines[k], "cpd_clone_occurrences": file_dup_clones[k]}
            for k in sorted(file_dup_lines)
        ]
    )
    meta = {
        "clone_groups_min_100_tokens": len(clone_groups),
        "total_duplicated_lines_across_occurrences": sum(g["lines"] * g["occurrences"] for g in clone_groups),
        "unique_files_with_clones": len(cpd_df),
        "largest_clones": sorted(clone_groups, key=lambda x: (x["tokens"], x["lines"]), reverse=True)[:10],
    }
    return meta, cpd_df


def main() -> None:
    scc = pd.read_csv(STAGE1_DIR / "scc_java_files.csv", encoding="utf-8")
    scc["file_path"] = scc["Provider"].astype(str).map(normalize_repo_path)
    scc = scc.rename(
        columns={
            "Lines": "scc_lines",
            "Code": "scc_sloc",
            "Comments": "scc_comments",
            "Blanks": "scc_blanks",
            "Complexity": "scc_complexity",
        }
    )
    scc["is_main"] = scc["file_path"].str.contains("/src/main/java/", regex=False)
    scc["is_test"] = scc["file_path"].str.contains("/src/test/", regex=False)
    scc["module"] = scc["file_path"].str.split("/").str[0]

    ck_classes, ck_file = build_ck()
    pmd_comp = build_pmd_complexity()
    pmd_smells_raw, pmd_smells_file = build_pmd_smells()
    cpd_meta, cpd_df = build_cpd_summary()
    evo = pd.read_csv(STAGE1_DIR / "git_file_evolution_24m.csv", encoding="utf-8")

    # Master dataset focused on production main Java files (and retaining all scc Java files)
    main_scc = scc[scc["is_main"]].copy()
    master = (
        main_scc[["file_path", "module", "scc_lines", "scc_sloc", "scc_comments", "scc_complexity"]]
        .merge(ck_file.drop(columns=["module"], errors="ignore"), on="file_path", how="left")
        .merge(pmd_comp, on="file_path", how="left")
        .merge(pmd_smells_file, on="file_path", how="left")
        .merge(cpd_df, on="file_path", how="left")
        .merge(
            evo[
                [
                    "file_path",
                    "commits_24m",
                    "commits_12m",
                    "lines_added_24m",
                    "lines_deleted_24m",
                    "total_churn_lines_24m",
                    "distinct_authors_24m",
                    "main_author_name",
                    "main_author_email",
                    "main_author_commits",
                    "main_author_share",
                    "main_author_active_6m",
                    "file_last_modified",
                ]
            ],
            on="file_path",
            how="left",
        )
    )

    # Fill numeric NaNs with 0 for counts/metrics where absence means 0 (smells, clones, churn)
    zero_fill_cols = [
        c
        for c in master.columns
        if c.startswith("smell_")
        or c.startswith("pmd_")
        or c.startswith("cpd_")
        or c in ("commits_24m", "commits_12m", "lines_added_24m", "lines_deleted_24m", "total_churn_lines_24m", "distinct_authors_24m", "main_author_commits")
    ]
    master[zero_fill_cols] = master[zero_fill_cols].fillna(0)
    master.to_csv(STAGE1_DIR / "stage1_master_java_metrics.csv", index=False)

    # Summary statistics
    summary = {
        "scc_total_java_files": int(len(scc)),
        "scc_main_java_files": int(len(main_scc)),
        "scc_test_java_files": int(scc["is_test"].sum()),
        "scc_main_sloc": int(main_scc["scc_sloc"].sum()),
        "scc_test_sloc": int(scc[scc["is_test"]]["scc_sloc"].sum()),
        "ck_total_classes_extracted": int(len(ck_classes)),
        "ck_unique_main_files": int(len(ck_file)),
        "ck_dit_max": int(ck_classes["dit"].max()),
        "ck_dit_mean": round(float(ck_classes["dit"].mean()), 2),
        "ck_cbo_max": int(ck_classes["cbo"].max()),
        "ck_cbo_mean": round(float(ck_classes["cbo"].mean()), 2),
        "ck_wmc_max": int(ck_classes["wmc"].max()),
        "ck_wmc_mean": round(float(ck_classes["wmc"].mean()), 2),
        "pmd_total_smells": int(len(pmd_smells_raw)),
        "pmd_smells_by_rule": pmd_smells_raw["Rule"].value_counts().to_dict(),
        "pmd_cog_sum_total": int(pmd_comp["pmd_cog_sum"].sum()),
        "pmd_cog_max_method": int(pmd_comp["pmd_cog_max"].max()),
        "pmd_cyclo_max_method": int(pmd_comp["pmd_cyclo_method_max"].max()),
        "cpd_summary": cpd_meta,
    }
    with (STAGE1_DIR / "stage1_summary_stats.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=== STAGE 1 CONSOLIDATED SUMMARY ===")
    print(f"Main Java files: {summary['scc_main_java_files']} (SLOC: {summary['scc_main_sloc']:,})")
    print(f"Test Java files: {summary['scc_test_java_files']} (SLOC: {summary['scc_test_sloc']:,})")
    print(f"CK classes extracted: {summary['ck_total_classes_extracted']} across {summary['ck_unique_main_files']} files")
    print(f"CK DIT mean/max: {summary['ck_dit_mean']} / {summary['ck_dit_max']}")
    print(f"CK CBO mean/max: {summary['ck_cbo_mean']} / {summary['ck_cbo_max']}")
    print(f"CK WMC mean/max: {summary['ck_wmc_mean']} / {summary['ck_wmc_max']}")
    print(f"PMD max method Cognitive / Cyclomatic: {summary['pmd_cog_max_method']} / {summary['pmd_cyclo_max_method']}")
    print(f"CPD clone groups (>=100 tokens): {cpd_meta['clone_groups_min_100_tokens']}")

    print("\n--- Top 10 by SLOC ---")
    print(master.sort_values("scc_sloc", ascending=False)[["file_path", "scc_sloc", "ck_primary_wmc", "ck_primary_cbo", "ck_primary_dit", "pmd_cog_sum", "pmd_total_smells", "commits_24m"]].head(10).to_string(index=False))

    print("\n--- Top 10 by Cognitive Complexity (file sum) ---")
    print(master.sort_values("pmd_cog_sum", ascending=False)[["file_path", "pmd_cog_sum", "pmd_cog_max", "pmd_cyclo_class_total", "scc_sloc", "ck_primary_cbo", "commits_24m"]].head(10).to_string(index=False))

    print("\n--- Top 10 by Churn (24m commits, main Java) ---")
    print(master.sort_values("commits_24m", ascending=False)[["file_path", "commits_24m", "commits_12m", "distinct_authors_24m", "main_author_share", "scc_sloc", "pmd_cog_sum"]].head(10).to_string(index=False))

    print("\n--- Top 10 by PMD Code Smells ---")
    print(master.sort_values("pmd_total_smells", ascending=False)[["file_path", "pmd_total_smells", "smell_GodClass", "smell_CognitiveComplexity", "smell_LawOfDemeter", "scc_sloc", "commits_24m"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
