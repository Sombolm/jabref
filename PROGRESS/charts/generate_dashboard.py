"""Generate a self-contained interactive HTML dashboard (PROGRESS/dashboard.html).

Embeds Stage 1 & Stage 2 datasets directly into static HTML/JS/CSS so the user can interactively
search, filter, sort, and inspect hotspots, coupling pairs, knowledge loss risks, code smells, and clones
locally in any browser. The "3D Explorer" and "Metric Correlations" tabs (explorer3d_panel.html +
explorer3d.js) use Plotly.js from the jsDelivr CDN, so those two tabs need an internet connection.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE1_DIR = REPO_ROOT / "PROGRESS" / "stage1"
STAGE2_DIR = REPO_ROOT / "PROGRESS" / "stage2"
OUT_HTML = REPO_ROOT / "PROGRESS" / "dashboard.html"
CHARTS_DIR = REPO_ROOT / "PROGRESS" / "charts"
PLOTLY_CDN = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"

# Metrics selectable in the 3D Explorer: (key, source column, label, group, description, log-scale by default)
EXPLORER_METRICS = [
    ("hs", "hotspot_score", "Hotspot Score", "Composite", "(0.5*Cog + 0.3*SLOC + 0.2*CBO, log-normalised) x log-normalised 24m commits, 0-100", False),
    ("sloc", "scc_sloc", "SLOC", "Size (scc)", "Source lines of code (scc, no blanks/comments)", True),
    ("comments", "scc_comments", "Comment lines", "Size (scc)", "Comment lines (scc)", True),
    ("commentRatio", "comment_ratio", "Comment ratio", "Size (scc)", "Comment lines / SLOC", False),
    ("wmc", "ck_primary_wmc", "WMC", "OO design (CK)", "Weighted Methods per Class (sum of method complexities) of the primary class", True),
    ("cbo", "ck_primary_cbo", "CBO", "OO design (CK)", "Coupling Between Objects: number of other classes this class depends on", True),
    ("fanin", "ck_fanin_max", "Fan-in", "OO design (CK)", "How many classes depend on this class (max over classes in file)", True),
    ("fanout", "ck_fanout_max", "Fan-out", "OO design (CK)", "How many classes this class depends on (max over classes in file)", True),
    ("rfc", "ck_primary_rfc", "RFC", "OO design (CK)", "Response For a Class: number of distinct methods that can be invoked", True),
    ("dit", "ck_primary_dit", "DIT", "OO design (CK)", "Depth of Inheritance Tree", False),
    ("lcom", "ck_primary_lcom_norm", "LCOM* (norm.)", "OO design (CK)", "Normalised Lack of Cohesion of Methods, 0 = cohesive, 1 = no cohesion", False),
    ("methods", "ck_methods_sum", "Methods", "OO design (CK)", "Number of methods (all classes in file)", True),
    ("fields", "ck_fields_sum", "Fields", "OO design (CK)", "Number of fields (all classes in file)", True),
    ("nest", "ck_max_nested_blocks", "Max nesting", "OO design (CK)", "Deepest block nesting level", False),
    ("cyc", "pmd_cyclo_class_total", "Cyclomatic (class)", "Complexity (PMD)", "PMD cyclomatic complexity, class total", True),
    ("cycMax", "pmd_cyclo_method_max", "Cyclomatic (max method)", "Complexity (PMD)", "Highest cyclomatic complexity of a single method", True),
    ("cog", "pmd_cog_sum", "Cognitive (sum)", "Complexity (PMD)", "Sum of PMD cognitive complexity over all methods", True),
    ("cogMax", "pmd_cog_max", "Cognitive (max method)", "Complexity (PMD)", "Highest cognitive complexity of a single method", True),
    ("cog15", "pmd_cog_methods_ge_15", "Methods with Cog >= 15", "Complexity (PMD)", "Number of methods over the usual cognitive complexity threshold (15)", True),
    ("smells", "pmd_total_smells", "PMD smells (total)", "Smells (PMD/CPD)", "All PMD design / dead-code violations in the file", True),
    ("lod", "smell_LawOfDemeter", "LawOfDemeter", "Smells (PMD/CPD)", "Law of Demeter violations (feature envy / train wrecks)", True),
    ("dup", "cpd_duplicated_lines", "Duplicated lines", "Smells (PMD/CPD)", "Lines in CPD clones (>= 100 tokens)", True),
    ("c24", "commits_24m", "Commits 24m", "Evolution (Git)", "Non-merge commits touching the file in the last 24 months", True),
    ("c12", "commits_12m", "Commits 12m", "Evolution (Git)", "Non-merge commits touching the file in the last 12 months", True),
    ("churn", "total_churn_lines_24m", "Churn lines 24m", "Evolution (Git)", "Lines added + deleted in the last 24 months", True),
    ("auth", "distinct_authors_24m", "Authors 24m", "Ownership (Git)", "Distinct authors in the last 24 months (1 = Bus Factor 1)", True),
    ("share", "main_author_share_pct", "Main author share %", "Ownership (Git)", "Share of 24m commits by the main author", False),
]


def load_cpd_clones() -> list[dict]:
    clones = []
    cpd_path = STAGE1_DIR / "pmd_cpd_main.csv"
    with cpd_path.open("r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            lines = int(row[0])
            tokens = int(row[1])
            occ = int(row[2])
            files = []
            idx = 3
            while idx + 1 < len(row):
                start_line = row[idx]
                p = row[idx + 1].replace("\\", "/")
                for marker in ("/jablib/", "/jabgui/", "/jabkit/", "/jabls/", "/jabls-cli/", "/jabsrv/", "/jabsrv-cli/"):
                    pos = p.find(marker)
                    if pos != -1:
                        p = p[pos + 1 :]
                        break
                files.append(f"{p}:{start_line}")
                idx += 2
            clones.append({"lines": lines, "tokens": tokens, "occurrences": occ, "locations": files})
    clones.sort(key=lambda x: (x["tokens"], x["lines"]), reverse=True)
    return clones


def build_explorer(df: pd.DataFrame) -> dict:
    """Columnar per-file metric table + Spearman correlation matrix for the 3D Explorer tab."""
    d = df.sort_values("hotspot_score", ascending=False).reset_index(drop=True).copy()
    d["comment_ratio"] = (d["scc_comments"] / d["scc_sloc"].replace(0, np.nan)).round(3)
    d["main_author_share_pct"] = (d["main_author_share"] * 100).round(1)

    def clean(v):
        if pd.isna(v):
            return None
        v = float(v)
        return int(v) if v.is_integer() else round(v, 3)

    numeric = pd.DataFrame({key: pd.to_numeric(d[col], errors="coerce") for key, col, *_ in EXPLORER_METRICS})
    corr = numeric.corr(method="spearman", min_periods=30)
    active = d["main_author_active_6m"].map(lambda v: True if pd.isna(v) else str(v).strip().lower() in ("true", "1"))
    return {
        "metrics": [{"k": k, "label": lbl, "g": grp, "d": desc, "log": log} for k, _, lbl, grp, desc, log in EXPLORER_METRICS],
        "files": d["file_path"].tolist(),
        "names": [Path(f).stem for f in d["file_path"]],
        "module": d["module"].tolist(),
        "owner": d["main_author_name"].fillna("").astype(str).tolist(),
        "active": active.tolist(),
        "god": (d["smell_GodClass"].fillna(0) > 0).tolist(),
        "cols": {k: [clean(v) for v in numeric[k]] for k in numeric.columns},
        "corr": {"keys": list(corr.columns), "rho": [[clean(v) for v in row] for row in corr.values]},
    }


def main() -> None:
    master = pd.read_csv(STAGE1_DIR / "stage1_master_java_metrics.csv")
    s1_stats = json.loads((STAGE1_DIR / "stage1_summary_stats.json").read_text(encoding="utf-8"))
    evo_meta = json.loads((STAGE1_DIR / "git_evolution_meta.json").read_text(encoding="utf-8"))
    hotspots = pd.read_csv(STAGE2_DIR / "stage2_hotspots_top25.csv")
    coupling = pd.read_csv(STAGE2_DIR / "stage2_logical_coupling_gt70.csv")
    kl_df = pd.read_csv(STAGE2_DIR / "stage2_knowledge_loss_risk.csv")
    clones = load_cpd_clones()

    # Recompute hotspot_score for all code files so every row in explorer has it
    df = master[
        ~master["file_path"].str.endswith("module-info.java")
        & ~master["file_path"].str.endswith("package-info.java")
    ].copy()
    norm_cog = np.log1p(df["pmd_cog_sum"]) / np.log1p(df["pmd_cog_sum"].max())
    norm_sloc = np.log1p(df["scc_sloc"]) / np.log1p(df["scc_sloc"].max())
    norm_cbo = np.log1p(df["ck_primary_cbo"].fillna(0)) / np.log1p(df["ck_primary_cbo"].fillna(0).max())
    norm_churn = np.log1p(df["commits_24m"]) / np.log1p(df["commits_24m"].max())
    df["hotspot_score"] = ((0.50 * norm_cog + 0.30 * norm_sloc + 0.20 * norm_cbo) * norm_churn * 100.0).round(2)

    classes_records = []
    for r in df.sort_values("hotspot_score", ascending=False).itertuples(index=False):
        classes_records.append(
            {
                "f": r.file_path,
                "n": Path(r.file_path).stem,
                "m": r.module,
                "hs": float(r.hotspot_score),
                "sloc": int(r.scc_sloc),
                "cog": int(r.pmd_cog_sum),
                "cogMax": int(r.pmd_cog_max),
                "cyc": int(r.pmd_cyclo_class_total),
                "wmc": int(r.ck_primary_wmc) if pd.notna(r.ck_primary_wmc) else 0,
                "cbo": int(r.ck_primary_cbo) if pd.notna(r.ck_primary_cbo) else 0,
                "dit": int(r.ck_primary_dit) if pd.notna(r.ck_primary_dit) else 0,
                "smells": int(r.pmd_total_smells),
                "god": int(getattr(r, "smell_GodClass", 0)),
                "c24": int(r.commits_24m),
                "c12": int(r.commits_12m),
                "auth": int(r.distinct_authors_24m),
                "share": round(float(r.main_author_share) * 100, 1) if pd.notna(r.main_author_share) else 0.0,
                "act": bool(r.main_author_active_6m) if pd.notna(r.main_author_active_6m) else True,
                "owner": str(r.main_author_name) if pd.notna(r.main_author_name) else "",
            }
        )

    coupling_records = coupling.fillna("").to_dict(orient="records")
    kl_records = kl_df.fillna("").to_dict(orient="records")

    payload = {
        "meta": {
            "repo": "JabRef/jabref",
            "fork": "Sombolm/jabref",
            "baseline": evo_meta["baseline_commit"][:10],
            "main_files": s1_stats["scc_main_java_files"],
            "main_sloc": s1_stats["scc_main_sloc"],
            "test_sloc": s1_stats["scc_test_sloc"],
            "commits_24m": evo_meta["non_merge_commits_analyzed"],
            "authors_24m": evo_meta["distinct_authors_24m"],
            "active_authors_6m": evo_meta["active_authors_6m"],
            "total_smells": s1_stats["pmd_total_smells"],
            "god_classes": s1_stats["pmd_smells_by_rule"].get("GodClass", 0),
            "cpd_clones": s1_stats["cpd_summary"]["clone_groups_min_100_tokens"],
            "top5": hotspots["file_path"].head(5).tolist(),
        },
        "smells_by_rule": s1_stats["pmd_smells_by_rule"],
        "classes": classes_records,
        "coupling": coupling_records,
        "knowledge_loss": kl_records,
        "clones": clones,
        "explorer": build_explorer(df),
    }
    explorer_panel = (CHARTS_DIR / "explorer3d_panel.html").read_text(encoding="utf-8")
    explorer_js = (CHARTS_DIR / "explorer3d.js").read_text(encoding="utf-8")

    data_json = json.dumps(payload, separators=(",", ":"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JabRef Maintainability Audit — Interactive Explorer</title>
<script src="{PLOTLY_CDN}"></script>
<style>
  :root {{
    --bg: #0f172a; --card: #1e293b; --card2: #273549; --border: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8; --danger: #f87171;
    --warn: #fbbf24; --ok: #4ade80;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.45; }}
  header {{ padding: 18px 28px; background: #0b1120; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
  header h1 {{ margin: 0; font-size: 1.35rem; }}
  header .sub {{ color: var(--muted); font-size: 0.85rem; }}
  .btn {{ background: var(--accent); color: #0b1120; border: none; padding: 8px 14px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.85rem; }}
  .btn:hover {{ opacity: 0.9; }}
  main {{ max-width: 1440px; margin: 0 auto; padding: 20px 24px 48px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
  .kpi .lbl {{ font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi .val {{ font-size: 1.55rem; font-weight: 700; margin-top: 4px; color: var(--accent); }}
  .kpi .sub {{ font-size: 0.78rem; color: var(--muted); margin-top: 2px; }}
  .tabs {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }}
  .tab {{ background: var(--card); color: var(--muted); border: 1px solid var(--border); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.88rem; }}
  .tab.active {{ background: var(--accent); color: #0b1120; border-color: var(--accent); }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
  .controls {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }}
  input, select {{ background: #0f172a; color: var(--text); border: 1px solid var(--border); padding: 7px 10px; border-radius: 6px; font-size: 0.88rem; }}
  input[type="text"] {{ min-width: 260px; }}
  label.chk {{ display: flex; align-items: center; gap: 6px; font-size: 0.86rem; color: var(--muted); cursor: pointer; }}
  .table-wrap {{ overflow-x: auto; max-height: 580px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; }}
  th {{ position: sticky; top: 0; background: #162032; color: var(--muted); text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; white-space: nowrap; }}
  th:hover {{ color: var(--text); }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #263244; white-space: nowrap; }}
  tr:hover td {{ background: var(--card2); }}
  .path {{ max-width: 440px; overflow: hidden; text-overflow: ellipsis; font-family: ui-monospace, Consolas, monospace; font-size: 0.8rem; color: #cbd5e1; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 0.74rem; font-weight: 600; }}
  .b-red {{ background: rgba(248,113,113,0.18); color: var(--danger); }}
  .b-warn {{ background: rgba(251,191,36,0.18); color: var(--warn); }}
  .b-ok {{ background: rgba(74,222,128,0.18); color: var(--ok); }}
  .b-blue {{ background: rgba(56,189,248,0.18); color: var(--accent); }}
  #scatter-box {{ position: relative; }}
  #tooltip {{ position: fixed; display: none; pointer-events: none; background: #0b1120; border: 1px solid var(--accent); border-radius: 8px; padding: 8px 11px; font-size: 0.8rem; z-index: 100; max-width: 360px; box-shadow: 0 8px 24px rgba(0,0,0,0.45); }}
  .bar-row {{ display: grid; grid-template-columns: 200px 1fr 60px; align-items: center; gap: 10px; margin-bottom: 7px; font-size: 0.84rem; }}
  .bar-track {{ background: #0f172a; border-radius: 4px; height: 16px; overflow: hidden; }}
  .bar-fill {{ background: linear-gradient(90deg, #38bdf8, #818cf8); height: 100%; }}
  @media print {{
    body {{ background: #fff; color: #000; }}
    .btn, .tabs, .controls {{ display: none !important; }}
    .panel {{ display: block !important; page-break-inside: avoid; }}
    .card, .kpi {{ background: #fff; border: 1px solid #ccc; color: #000; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
  }}
</style>
</head>
<body>
<header>
  <div>
    <h1>JabRef Maintainability Audit — Interactive Explorer</h1>
    <div class="sub">Repo: <strong id="h-repo"></strong> | Baseline: <code id="h-base"></code> | 24-month Git window + Static AST/Smell Scan</div>
  </div>
  <button class="btn" onclick="window.print()">Print / Save PDF</button>
</header>

<main>
  <div class="kpis" id="kpis"></div>

  <div class="tabs">
    <button class="tab active" onclick="showTab('matrix', this)">Hotspot Matrix &amp; Top 5</button>
    <button class="tab" onclick="showTab('classes', this)">All Classes Explorer (2,298)</button>
    <button class="tab" onclick="showTab('coupling', this)">Logical Coupling (&gt;70%)</button>
    <button class="tab" onclick="showTab('bus', this)">Knowledge Loss (Bus Factor = 1)</button>
    <button class="tab" onclick="showTab('smells', this)">Code Smells &amp; CPD Clones</button>
    <button class="tab" id="tabbtn-explorer3d" onclick="showTab('explorer3d', this)">3D Explorer</button>
    <button class="tab" id="tabbtn-corr" onclick="showTab('corr', this)">Metric Correlations</button>
  </div>

  <section id="panel-matrix" class="panel active">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
        <div>
          <strong>Interactive Hotspot Matrix: Cognitive Complexity vs. 24-Month Commits</strong>
          <div class="sub">Hover any bubble to inspect metrics. Blue rings mark the Top 5 Hotspots; bubble size = SLOC.</div>
        </div>
        <select id="matrix-mod" onchange="drawMatrix()">
          <option value="ALL">All Modules</option>
          <option value="jablib">jablib</option>
          <option value="jabgui">jabgui</option>
          <option value="jabsrv">jabsrv</option>
          <option value="jabkit">jabkit</option>
          <option value="jabls">jabls</option>
        </select>
      </div>
      <div id="scatter-box">
        <svg id="matrix-svg" viewBox="0 0 1100 500" style="width:100%;height:auto;background:#0b1120;border-radius:8px;border:1px solid #334155;"></svg>
      </div>
    </div>
    <div class="card">
      <strong>Top 10 Critical Hotspots (Complexity × Change Frequency)</strong>
      <div class="table-wrap" style="margin-top:10px;">
        <table id="top10-table"></table>
      </div>
    </div>
  </section>

  <section id="panel-classes" class="panel">
    <div class="card">
      <div class="controls">
        <input type="text" id="cls-search" placeholder="Search class or file path..." oninput="renderClasses()">
        <select id="cls-mod" onchange="renderClasses()">
          <option value="ALL">All Modules</option>
          <option value="jablib">jablib</option>
          <option value="jabgui">jabgui</option>
          <option value="jabsrv">jabsrv</option>
          <option value="jabkit">jabkit</option>
          <option value="jabls">jabls</option>
        </select>
        <label class="chk"><input type="checkbox" id="cls-god" onchange="renderClasses()"> GodClass only</label>
        <label class="chk"><input type="checkbox" id="cls-bf1" onchange="renderClasses()"> Bus Factor = 1 (24m)</label>
        <span class="sub" id="cls-count"></span>
      </div>
      <div class="table-wrap">
        <table id="classes-table"></table>
      </div>
    </div>
  </section>

  <section id="panel-coupling" class="panel">
    <div class="card">
      <div class="controls">
        <label class="chk"><input type="checkbox" id="cpl-nodep" checked onchange="renderCoupling()"> Only pairs WITHOUT direct architectural dependency</label>
        <label class="chk"><input type="checkbox" id="cpl-nomanifest" checked onchange="renderCoupling()"> Hide module-info.java manifests</label>
        <span class="sub" id="cpl-count"></span>
      </div>
      <div class="table-wrap">
        <table id="coupling-table"></table>
      </div>
    </div>
  </section>

  <section id="panel-bus" class="panel">
    <div class="card">
      <div class="controls">
        <label class="chk"><input type="checkbox" id="kl-inactive" onchange="renderKL()"> Inactive main author (&gt;6m) only</label>
        <label class="chk"><input type="checkbox" id="kl-bf1" onchange="renderKL()"> All-time Bus Factor = 1 only</label>
        <span class="sub" id="kl-count"></span>
      </div>
      <div class="table-wrap">
        <table id="kl-table"></table>
      </div>
    </div>
  </section>

  <section id="panel-smells" class="panel">
    <div class="card">
      <strong>PMD Code Smells Distribution (Production Java, Total = 3,007)</strong>
      <div id="smells-bars" style="margin-top:12px;"></div>
    </div>
    <div class="card">
      <strong>PMD CPD Duplicated Code Blocks (&gt;= 100 tokens, Total = 28 clone groups)</strong>
      <div class="table-wrap" style="margin-top:10px;">
        <table id="clones-table"></table>
      </div>
    </div>
  </section>
{explorer_panel}
</main>

<div id="tooltip"></div>

<script>
const DATA = {data_json};

function showTab(id, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  btn.classList.add('active');
  if (window.onTabShown) window.onTabShown(id);
}}

function initKPIs() {{
  const m = DATA.meta;
  document.getElementById('h-repo').textContent = m.repo + ' (fork: ' + m.fork + ')';
  document.getElementById('h-base').textContent = m.baseline;
  const kpis = [
    ['Production SLOC', m.main_sloc.toLocaleString(), m.main_files.toLocaleString() + ' Java files (+' + m.test_sloc.toLocaleString() + ' test SLOC)'],
    ['PMD Code Smells', m.total_smells.toLocaleString(), m.god_classes + ' God Classes | ' + m.cpd_clones + ' CPD clones'],
    ['24m Commits', m.commits_24m.toLocaleString(), m.authors_24m + ' authors (' + m.active_authors_6m + ' active <=6m)'],
    ['Top Hotspot Score', DATA.classes[0].hs, DATA.classes[0].n + ' (' + DATA.classes[0].c24 + 'c, ' + DATA.classes[0].sloc + ' SLOC)'],
    ['Hidden Coupling (>70%)', DATA.coupling.filter(r => !r.has_direct_dep && !r.is_module_info).length, 'non-manifest pairs w/o direct dep'],
    ['Inactive Single-Owner', DATA.classes.filter(c => !c.act && c.share >= 65 && c.sloc >= 100).length, 'files >=100 SLOC, owner inactive >6m']
  ];
  document.getElementById('kpis').innerHTML = kpis.map(([l,v,s]) =>
    `<div class="kpi"><div class="lbl">${{l}}</div><div class="val">${{v}}</div><div class="sub">${{s}}</div></div>`
  ).join('');
}}

function drawMatrix() {{
  const svg = document.getElementById('matrix-svg');
  const mod = document.getElementById('matrix-mod').value;
  const pts = DATA.classes.filter(c => mod === 'ALL' || c.m === mod);
  const W = 1100, H = 500, padL = 64, padR = 28, padT = 26, padB = 46;
  const maxX = Math.max(125, ...pts.map(p => p.c24));
  const maxY = Math.max(520, ...pts.map(p => p.cog));
  const sx = x => padL + (x / maxX) * (W - padL - padR);
  const sy = y => H - padB - (y / maxY) * (H - padT - padB);
  const top5Set = new Set(DATA.meta.top5);

  let html = '';
  for (let gx = 0; gx <= maxX; gx += 20) {{
    const x = sx(gx);
    html += `<line x1="${{x}}" y1="${{padT}}" x2="${{x}}" y2="${{H-padB}}" stroke="#1e293b" stroke-width="1"/>`;
    html += `<text x="${{x}}" y="${{H-padB+18}}" fill="#94a3b8" font-size="11" text-anchor="middle">${{gx}}</text>`;
  }}
  for (let gy = 0; gy <= maxY; gy += 100) {{
    const y = sy(gy);
    html += `<line x1="${{padL}}" y1="${{y}}" x2="${{W-padR}}" y2="${{y}}" stroke="#1e293b" stroke-width="1"/>`;
    html += `<text x="${{padL-10}}" y="${{y+4}}" fill="#94a3b8" font-size="11" text-anchor="end">${{gy}}</text>`;
  }}
  html += `<text x="${{W/2}}" y="${{H-8}}" fill="#cbd5e1" font-size="12" text-anchor="middle">24-Month Change Frequency (Commits)</text>`;
  html += `<text x="16" y="${{H/2}}" fill="#cbd5e1" font-size="12" text-anchor="middle" transform="rotate(-90 16 ${{H/2}})">Total Cognitive Complexity (PMD)</text>`;

  // Draw normal points first, top5 last
  const ordered = [...pts].sort((a,b) => (top5Set.has(a.f)?1:0) - (top5Set.has(b.f)?1:0));
  ordered.forEach((p, idx) => {{
    const cx = sx(p.c24), cy = sy(p.cog);
    const r = Math.min(18, Math.max(3, Math.sqrt(p.sloc) / 2.6));
    const isTop = top5Set.has(p.f);
    const color = p.cbo >= 60 ? '#ef4444' : (p.cbo >= 25 ? '#f59e0b' : '#38bdf8');
    const stroke = isTop ? '#ffffff' : '#0f172a';
    const sw = isTop ? 2.4 : 0.7;
    html += `<circle cx="${{cx.toFixed(1)}}" cy="${{cy.toFixed(1)}}" r="${{r.toFixed(1)}}" fill="${{color}}" fill-opacity="${{isTop?0.95:0.65}}" stroke="${{stroke}}" stroke-width="${{sw}}" data-path="${{p.f}}" onmousemove="showTip(evt, this)" onmouseleave="hideTip()"/>`;
    if (isTop || p.cog >= 280) {{
      html += `<text x="${{(cx+r+4).toFixed(1)}}" y="${{(cy+3).toFixed(1)}}" fill="${{isTop?'#f8fafc':'#94a3b8'}}" font-size="${{isTop?11.5:10}}" font-weight="${{isTop?700:400}}">${{p.n}}</text>`;
    }}
  }});
  svg.innerHTML = html;
}}

const clsByPath = new Map(DATA.classes.map(c => [c.f, c]));
function showTip(evt, el) {{
  const p = clsByPath.get(el.getAttribute('data-path'));
  if (!p) return;
  const tip = document.getElementById('tooltip');
  tip.innerHTML = `<strong>${{p.n}}</strong> <span class="badge b-blue">${{p.m}}</span><br>
    <span style="color:#94a3b8;font-size:0.74rem;">${{p.f}}</span><br>
    Hotspot Score: <strong>${{p.hs}}</strong> | Commits: <strong>${{p.c24}}</strong> (12m: ${{p.c12}})<br>
    SLOC: <strong>${{p.sloc}}</strong> | Cog Sum: <strong>${{p.cog}}</strong> (max ${{p.cogMax}})<br>
    CBO: <strong>${{p.cbo}}</strong> | DIT: <strong>${{p.dit}}</strong> | Smells: <strong>${{p.smells}}</strong> | Authors: <strong>${{p.auth}}</strong>`;
  tip.style.display = 'block';
  tip.style.left = Math.min(window.innerWidth - 380, evt.clientX + 14) + 'px';
  tip.style.top = Math.min(window.innerHeight - 140, evt.clientY + 14) + 'px';
}}
function hideTip() {{ document.getElementById('tooltip').style.display = 'none'; }}

let sortKey = 'hs', sortAsc = false;
function setSort(k) {{
  if (sortKey === k) sortAsc = !sortAsc;
  else {{ sortKey = k; sortAsc = false; }}
  renderClasses();
}}

function renderTop10() {{
  const top10 = DATA.classes.slice(0, 10);
  document.getElementById('top10-table').innerHTML =
    `<thead><tr><th>#</th><th>Class</th><th>Module</th><th>Hotspot</th><th>24m (12m)</th><th>SLOC</th><th>Cog Sum</th><th>CBO</th><th>DIT</th><th>Smells</th><th>God</th><th>Authors</th></tr></thead><tbody>` +
    top10.map((c,i) => `<tr>
      <td><strong>#${{i+1}}</strong></td>
      <td><strong>${{c.n}}</strong><div class="path" title="${{c.f}}">${{c.f}}</div></td>
      <td><span class="badge b-blue">${{c.m}}</span></td>
      <td><strong>${{c.hs}}</strong></td>
      <td>${{c.c24}} (${{c.c12}})</td>
      <td>${{c.sloc}}</td>
      <td>${{c.cog}}</td>
      <td>${{c.cbo}}</td>
      <td>${{c.dit}}</td>
      <td>${{c.smells}}</td>
      <td>${{c.god ? '<span class="badge b-red">Yes</span>' : '-'}}</td>
      <td>${{c.auth}}</td>
    </tr>`).join('') + `</tbody>`;
}}

function renderClasses() {{
  const q = document.getElementById('cls-search').value.toLowerCase();
  const mod = document.getElementById('cls-mod').value;
  const god = document.getElementById('cls-god').checked;
  const bf1 = document.getElementById('cls-bf1').checked;
  let rows = DATA.classes.filter(c =>
    (mod === 'ALL' || c.m === mod) &&
    (!god || c.god > 0) &&
    (!bf1 || c.auth === 1) &&
    (!q || c.f.toLowerCase().includes(q))
  );
  rows.sort((a,b) => {{
    const va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  }});
  document.getElementById('cls-count').textContent = `Showing ${{Math.min(rows.length, 250)}} of ${{rows.length}} matching files`;
  const cols = [['n','Class'],['m','Module'],['hs','Hotspot'],['c24','24m'],['sloc','SLOC'],['cog','Cog Sum'],['cogMax','Cog Max'],['cbo','CBO'],['dit','DIT'],['smells','Smells'],['auth','Authors'],['share','Owner %']];
  const thead = '<thead><tr>' + cols.map(([k,lbl]) => `<th onclick="setSort('${{k}}')">${{lbl}} ${{sortKey===k?(sortAsc?'▲':'▼'):''}}</th>`).join('') + '</tr></thead>';
  const tbody = '<tbody>' + rows.slice(0, 250).map(c => `<tr>
    <td><strong>${{c.n}}</strong><div class="path" title="${{c.f}}">${{c.f}}</div></td>
    <td><span class="badge b-blue">${{c.m}}</span></td>
    <td><strong>${{c.hs}}</strong></td>
    <td>${{c.c24}}</td><td>${{c.sloc}}</td><td>${{c.cog}}</td><td>${{c.cogMax}}</td>
    <td>${{c.cbo}}</td><td>${{c.dit}}</td><td>${{c.smells}}</td><td>${{c.auth}}</td>
    <td>${{c.share}}% ${{c.act ? '' : '<span class="badge b-red">inactive</span>'}}</td>
  </tr>`).join('') + '</tbody>';
  document.getElementById('classes-table').innerHTML = thead + tbody;
}}

function renderCoupling() {{
  const noDep = document.getElementById('cpl-nodep').checked;
  const noMan = document.getElementById('cpl-nomanifest').checked;
  const rows = DATA.coupling.filter(r => (!noDep || !r.has_direct_dep) && (!noMan || !r.is_module_info));
  document.getElementById('cpl-count').textContent = `${{rows.length}} pairs shown`;
  document.getElementById('coupling-table').innerHTML =
    `<thead><tr><th>File A</th><th>File B</th><th>Shared</th><th>A / B Commits</th><th>A→B</th><th>B→A</th><th>Direct Dep?</th></tr></thead><tbody>` +
    rows.map(r => `<tr>
      <td><div class="path" title="${{r.file_a}}">${{r.file_a}}</div></td>
      <td><div class="path" title="${{r.file_b}}">${{r.file_b}}</div></td>
      <td><strong>${{r.shared_commits}}</strong></td>
      <td>${{r.commits_a}} / ${{r.commits_b}}</td>
      <td>${{(r.confidence_a_to_b*100).toFixed(1)}}%</td>
      <td>${{(r.confidence_b_to_a*100).toFixed(1)}}%</td>
      <td>${{r.has_direct_dep ? '<span class="badge b-warn">' + r.dep_reason + '</span>' : '<span class="badge b-red">None (Logical)</span>'}}</td>
    </tr>`).join('') + `</tbody>`;
}}

function renderKL() {{
  const inact = document.getElementById('kl-inactive').checked;
  const bf1 = document.getElementById('kl-bf1').checked;
  const rows = DATA.knowledge_loss.filter(r => (!inact || !r.all_time_top_active_6m || !r.main_author_active_6m) && (!bf1 || r.all_time_authors === 1));
  document.getElementById('kl-count').textContent = `${{rows.length}} components shown`;
  document.getElementById('kl-table').innerHTML =
    `<thead><tr><th>Component</th><th>SLOC</th><th>Cog</th><th>CBO</th><th>24m Authors</th><th>All-Time Authors</th><th>Top Owner</th><th>All-Time Share</th><th>Active <=6m?</th></tr></thead><tbody>` +
    rows.map(r => `<tr>
      <td><div class="path" title="${{r.file_path}}">${{r.file_path}}</div></td>
      <td>${{r.scc_sloc}}</td><td>${{r.pmd_cog_sum}}</td><td>${{r.ck_primary_cbo || '-'}}</td>
      <td>${{r.distinct_authors_24m}}</td><td><strong>${{r.all_time_authors}}</strong></td>
      <td>${{r.all_time_top_author}}</td><td>${{(r.all_time_top_share*100).toFixed(1)}}%</td>
      <td>${{r.all_time_top_active_6m ? '<span class="badge b-ok">Active</span>' : '<span class="badge b-red">Inactive</span>'}}</td>
    </tr>`).join('') + `</tbody>`;
}}

function renderSmells() {{
  const entries = Object.entries(DATA.smells_by_rule).sort((a,b) => b[1]-a[1]);
  const maxVal = entries[0][1];
  document.getElementById('smells-bars').innerHTML = entries.map(([k,v]) =>
    `<div class="bar-row"><div>${{k}}</div><div class="bar-track"><div class="bar-fill" style="width:${{(v/maxVal*100).toFixed(1)}}%"></div></div><div><strong>${{v}}</strong></div></div>`
  ).join('');
  document.getElementById('clones-table').innerHTML =
    `<thead><tr><th>Lines</th><th>Tokens</th><th>Occurrences</th><th>Locations</th></tr></thead><tbody>` +
    DATA.clones.map(c => `<tr>
      <td>${{c.lines}}</td><td><strong>${{c.tokens}}</strong></td><td>${{c.occurrences}}</td>
      <td>${{c.locations.map(l => `<div class="path">${{l}}</div>`).join('')}}</td>
    </tr>`).join('') + `</tbody>`;
}}

initKPIs();
drawMatrix();
renderTop10();
renderClasses();
renderCoupling();
renderKL();
renderSmells();

{explorer_js}
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Saved interactive dashboard: {OUT_HTML} ({OUT_HTML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
