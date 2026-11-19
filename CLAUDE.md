# System Maintainability Audit & Refactoring Plan — JabRef

> **SYNC & RESULTS RULES:**
> 1. **SYNC RULE (`CLAUDE.md` <-> `GEMINI.md`):** Whenever you update progress, complete a task, record findings, or adjust the plan, you MUST update **BOTH** `CLAUDE.md` and `GEMINI.md` so they remain synchronized.
> 2. **CENTRAL RESULTS RULE:** All key results, summary tables, top findings, and stage takeaways MUST be written in ONE central, easy-to-read place: **[`PROGRESS/SUMMARY.md`](./PROGRESS/SUMMARY.md)**. Raw exports (`csv`/`json`), scripts, and charts go into `PROGRESS/stage1/`, `PROGRESS/stage2/`, `PROGRESS/stage3/`, and `PROGRESS/charts/`.
> 3. **GIT WORKFLOW:** Commit and push progress regularly to our audit fork (`Sombolm/jabref`, branch `main`). Never commit `.audit-tools/` or `.venv/`, and never submit audit commits upstream to `JabRef/jabref`.

---

## 1. Selected Scope & Toolchain

- **Target Repository:** `JabRef/jabref` (Java) — Fork: `https://github.com/Sombolm/jabref` (branch `main`)
- **Baseline Analyzed Commit:** `454ee663981cf6c51b5fc3f190fb0ed0fcdf799b` (`2026-11-18`, excludes audit setup commits)
- **Central Readable Results:** [`PROGRESS/SUMMARY.md`](./PROGRESS/SUMMARY.md)
- **Toolchain (1 primary tool per category):**
  1. **Size Metrics:** `scc` (LOC, SLOC, files, language breakdown)
  2. **Complexity Analysis:** `PMD` (Cyclomatic Complexity & Cognitive Complexity)
  3. **Dependency & Coupling Analysis:** `CK` (`mauricioaniche/ck` — LOC, WMC, DIT, CBO, LCOM, RFC)
  4. **Code Smells & Duplication Detection:** `PMD` + `PMD CPD` (God Class, Long Method, Coupling smells, Copy/Paste Detector)
  5. **Evolutionary & Behavioral Analysis:** `PyDriller` + `git log` (12–24 months commit history: Churn, Ownership/Bus Factor, Temporal Coupling)

---

## 2. Assignment Specification (Hierarchical)

### Objective
Conduct a comprehensive internal quality assessment of `JabRef/jabref` combining **static code analysis**, **code smell detection**, and **evolutionary (behavioral) code analysis** to identify critical maintainability bottlenecks (hotspots), determine their root causes, and propose a prioritized refactoring plan.

### Stage 1: Data Collection
Analyze the current state of `main` and Git history, extracting raw metrics across three dimensions:

- **Task 1.1: Static Code Metrics**
  - Target branch: current state of `main` (at baseline `454ee66398`)
  - Granularity: file / class level
  - Required metrics: `LOC`, `Cyclomatic Complexity`, `Cognitive Complexity`, `DIT`, `CBO`
- **Task 1.2: Code Smells Detection**
  - Scan the codebase for maintainability issues
  - Export most frequent & most severe smells (God Class / Blob, Long Method, Feature Envy / excessive coupling, Duplicated Code, Shotgun Surgery)
- **Task 1.3: Repository Evolution Metrics**
  - Time window: last **12 to 24 months** of Git commit history
  - Required metrics: **Change Frequency (Churn)**, **Code Ownership** (distinct authors & % main author), **Temporal (Logical) Coupling**

### Stage 2: Data Correlation & Hotspot Analysis
- **Task 2.1: Hotspot Identification** — Overlay Complexity (`Cognitive Complexity` / `LOC`) with `Change Frequency`; identify **top 5 critical hotspots**
- **Task 2.2: Logical Coupling Analysis** — Pairs with high co-change (`> 70%` shared commits) lacking direct architectural dependency
- **Task 2.3: Knowledge Loss Risk** — Complex core components with `Bus Factor = 1` (especially inactive authors)

### Stage 3: Root Cause Analysis (RCA) & Action Plan
Select **top 3 to 5 most critical issues** from Stage 2:
- **Task 3.1: Symptoms vs. Root Causes** — Quantitative evidence + structural/process root causes
- **Task 3.2: Refactoring Solutions** — Concrete architectural/code refactorings
- **Task 3.3: Prioritization** — Rank by Cost & Risk (unit test coverage) and Business & Technical Impact

### Deliverable: Final Audit Report
1. Executive Summary (1–5 rating + justification)
2. Methodology & Setup (URL, commit range, repo size, tool configs)
3. Data Visualizations (Complexity vs. Churn Hotspot Matrix, Code Smell distribution)
4. Diagnostic Cards (Top 3–5 Issues)
5. Prioritized Roadmap (Quick Wins vs. Strategic Refactoring)

---

## 3. Progress Tracker

- [x] **Setup:** Fork `JabRef/jabref` -> `Sombolm/jabref`, clone locally, create `PROGRESS/`, `PROGRESS/SUMMARY.md`, and synchronized `GEMINI.md` / `CLAUDE.md`
- [x] **Stage 1: Data Collection** *(completed — raw exports in `PROGRESS/stage1/`, consolidated summary in [`PROGRESS/SUMMARY.md`](./PROGRESS/SUMMARY.md))*
  - [x] Task 1.1: Static Code Metrics (`scc` v4.1.0, `CK` 0.7.0, `PMD` 7.29.0)
  - [x] Task 1.2: Code Smells & Duplication Detection (`PMD` 3,007 smells, `PMD CPD` 28 clone groups)
  - [x] Task 1.3: Repository Evolution Metrics (`PyDriller` 2.12 — 4,330 non-merge commits over 24m)
- [x] **Stage 2: Data Correlation & Hotspot Analysis** *(completed — outputs in `PROGRESS/stage2/`, charts in `PROGRESS/charts/`, interactive explorer in `PROGRESS/dashboard.html` incl. 3D Metric Explorer & Spearman correlation matrix, summary in [`PROGRESS/SUMMARY.md`](./PROGRESS/SUMMARY.md))*
  - [x] Task 2.1: Hotspot Identification (Top 5 hotspots: `JabRefCliPreferences`, `LibraryTab`, `JabRefGuiPreferences`, `JabRefFrame`, `CitationRelationsTab`)
  - [x] Task 2.2: Logical Coupling Analysis (`11` non-manifest production pairs >70% co-change without direct dependency)
  - [x] Task 2.3: Knowledge Loss Risk (`7` inactive-owner files >=100 SLOC + all-time Bus Factor = 1 complex components)
- [ ] **Stage 3: Root Cause Analysis (RCA) & Action Plan**
  - [ ] Task 3.1: Symptoms vs. Root Causes (Top 3–5 issues)
  - [ ] Task 3.2: Refactoring Solutions
  - [ ] Task 3.3: Prioritization (test coverage check + impact)
- [ ] **Deliverable: Final Audit Report**
  - [ ] 1. Executive Summary
  - [ ] 2. Methodology & Setup
  - [ ] 3. Data Visualizations
  - [ ] 4. Diagnostic Cards (Top 3–5 Issues)
  - [ ] 5. Prioritized Roadmap
