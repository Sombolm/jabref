# System Maintainability Audit & Refactoring Plan — JabRef

> **SYNC RULE (CLAUDE.md <-> GEMINI.md):**
> This file (`CLAUDE.md`) and `GEMINI.md` are paired instructions and progress trackers for multi-environment work (Claude Code and Antigravity / Gemini).
> **Whenever you update progress, complete a task, record findings, or adjust the plan, you MUST update BOTH `CLAUDE.md` and `GEMINI.md` so they remain synchronized.**
> Save all analysis outputs, scripts, charts, and report drafts inside [`PROGRESS/`](./PROGRESS/).
> This is an audit fork (`Sombolm/jabref`) of `JabRef/jabref` — do not submit audit/progress commits upstream.

---

## 1. Selected Scope & Toolchain

- **Target Repository:** `JabRef/jabref` (Java) — Fork: `https://github.com/Sombolm/jabref` (branch `main`)
- **Output Directory:** `PROGRESS/`
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
  - Target branch: current state of `main`
  - Granularity: file / class level
  - Required metrics:
    - Lines of Code (`LOC`)
    - `Cyclomatic Complexity`
    - `Cognitive Complexity`
    - Depth of Inheritance Tree (`DIT`)
    - Coupling Between Objects (`CBO`)
- **Task 1.2: Code Smells Detection**
  - Scan the codebase for maintainability issues
  - Export a list of the most frequent and most severe code smells (e.g., God Class / Blob, Long Method, Feature Envy, Duplicated Code, Shotgun Surgery)
- **Task 1.3: Repository Evolution Metrics**
  - Time window: last **12 to 24 months** of Git commit history
  - Required metrics:
    - **Change Frequency (Churn):** number of commits modifying each file
    - **Code Ownership:** number of distinct authors per file and percentage of contributions by the main author
    - **Temporal (Logical) Coupling:** pairs or groups of files that frequently change together within the same commit

### Stage 2: Data Correlation & Hotspot Analysis
Combine static and historical data to find where quality issues actively hurt development:

- **Task 2.1: Hotspot Identification**
  - Overlay complexity metrics (`Cognitive Complexity` or `LOC`) with `Change Frequency`
  - Identify the **top 5 most critical hotspots** (files/modules that are both highly complex and frequently modified)
- **Task 2.2: Logical Coupling Analysis**
  - Identify pairs of files with high co-change (e.g., `> 70%` shared commits) that lack a direct architectural dependency (e.g., no inheritance or direct method calls)
- **Task 2.3: Knowledge Loss Risk**
  - Identify complex, core components maintained almost exclusively by a single developer (`Bus Factor = 1`), especially if that contributor is no longer active in the project

### Stage 3: Root Cause Analysis (RCA) & Action Plan
Select the **top 3 to 5 most critical issues** discovered in Stage 2 and perform a deep-dive investigation:

- **Task 3.1: Separating Symptoms from Root Causes**
  - Document **Symptoms (Quantitative Evidence):** exact metrics and detected smells (e.g., LOC, Cyclomatic/Cognitive Complexity, smell counts, commit churn)
  - Document **Probable Root Causes:** structural or process-wise explanation (e.g., SRP violation, missing Strategy/polymorphism, etc.)
- **Task 3.2: Refactoring Solutions**
  - Propose concrete refactoring techniques or architectural changes addressing the root cause rather than masking symptoms (e.g., Extract Class, Replace Conditional with Polymorphism, Introduce Interface to break logical coupling)
- **Task 3.3: Prioritization**
  - Rank the identified issues from highest to lowest priority
  - Justify ranking based on:
    - **Cost & Risk of Change:** check existing unit test coverage for the affected modules
    - **Business & Technical Impact:** how frequently the team touches this code and how much it slows down feature delivery

### Deliverable: Final Audit Report
Structured technical report containing:
1. **Executive Summary:** Overall maintainability rating (1–5 scale) with brief justification.
2. **Methodology & Setup:** Direct URL to the analyzed repository, commit range, repository size, and tool configurations.
3. **Data Visualizations:** Charts illustrating Complexity vs. Change Frequency (Hotspot matrix) and Code Smell distribution.
4. **Diagnostic Cards (Top 3–5 Issues):** Detailed breakdown of Symptoms, Root Causes, Refactoring Proposals, and Risk Assessment.
5. **Prioritized Roadmap:** Action plan divided into **Quick Wins** (low risk, immediate value) and **Strategic Refactoring** (long-term architectural improvements).

---

## 3. Progress Tracker

- [x] **Setup:** Fork `JabRef/jabref` -> `Sombolm/jabref`, clone locally, create `PROGRESS/`, create synchronized `GEMINI.md` and `CLAUDE.md`
- [ ] **Stage 1: Data Collection**
  - [ ] Task 1.1: Static Code Metrics (`scc`, `CK`, `PMD`)
  - [ ] Task 1.2: Code Smells & Duplication Detection (`PMD`, `PMD CPD`)
  - [ ] Task 1.3: Repository Evolution Metrics (`PyDriller` / `git log`, 12–24 months)
- [ ] **Stage 2: Data Correlation & Hotspot Analysis**
  - [ ] Task 2.1: Hotspot Identification (Top 5 hotspots)
  - [ ] Task 2.2: Logical Coupling Analysis (>70% co-change without direct dependency)
  - [ ] Task 2.3: Knowledge Loss Risk (Bus Factor = 1 on complex core components)
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
