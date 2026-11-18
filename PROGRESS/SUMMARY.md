# JabRef Maintainability Audit — Consolidated Results & Findings

> This is the **single central readable summary** of all key metrics, findings, and conclusions across Stages 1–3 of the audit of `JabRef/jabref` (baseline commit `454ee663981cf6c51b5fc3f190fb0ed0fcdf799b` on `main`, `2026-11-18`).
> Raw datasets, scripts, and charts are stored in `PROGRESS/stage1/`, `PROGRESS/stage2/`, `PROGRESS/stage3/`, and `PROGRESS/charts/`.

---

## Stage 1: Data Collection Summary

**Analyzed Scope:** `JabRef/jabref` (`main` at `454ee66398`), focusing static metrics & smell scans on production Java sources (`*/src/main/java`) while capturing full-repo size (`scc`) and 24-month Git history (`PyDriller`).

### 1.1 Repository Size (`scc` v4.1.0)
- **Entire Repository:** `4,073` files | `567,826` total lines | **`446,248` SLOC** | `32,335` comments | `89,243` blanks
- **Java Overall:** `3,289` files | `412,407` total lines | **`321,742` SLOC** (`72.1%` of repo SLOC)
- **Production vs. Test Java Split:**
  - Production (`*/src/main/java`): **`2,311` files**, **`208,262` SLOC**
  - Tests (`*/src/test/**`): **`966` files**, **`112,603` SLOC** (strong test footprint: ~0.54 test SLOC per main SLOC)
- Other notable file types: Properties (`36,767` SLOC — l10n bundles), JSON (`21,626` SLOC), Markdown (`16,018` SLOC), XML (`15,793` SLOC), FXML (`5,300` SLOC).

### 1.2 Static Code Metrics (`CK` 0.7.0 + `PMD` 7.29.0)
*(Extracted across `2,509` classes in `2,152` main Java files via `CK` across the 7 core modules, plus `25,098` method/class complexity records via `PMD` across `2,298` main Java files. Note: `jablib-examples` [3 files] was excluded from CK due to an Eclipse JDT `SwitchExpression` parser crash.)*

- **Aggregate CK Metrics (Class-level):**
  - **DIT (Depth of Inheritance Tree):** mean `1.40`, max **`8`**
  - **CBO (Coupling Between Objects):** mean `8.23`, max **`104`** (`JabRefCliPreferences`), followed by `LibraryTab` (`102`), `MainMenu` (`89`), `JabRefFrame` (`78`), `CitationRelationsTab` (`71`)
  - **WMC (Weighted Methods per Class):** mean `13.62`, max **`341`** (`MedlineImporter`), followed by `JabRefCliPreferences` (`302`), `BibtexParser` (`259`), `BracketedPattern` (`255`)
- **Aggregate PMD Complexity:**
  - **Total Cognitive Complexity (sum across main methods):** **`26,315`**; **max single-method Cognitive Complexity = `304`** (`RisImporter`), followed by `BracketedPattern` (`124`), `RTFChars` (`115`), `PdfContentImporter` (`98`), `AuthorListParser` (`88`), `ImportHandler` (`72`)
  - **Max single-method Cyclomatic Complexity = `148`**

#### Top 10 Production Java Files by SLOC & Static Complexity

| File | SLOC | CK WMC | CK CBO | CK DIT | PMD Cog. Sum | PMD Smells | 24m Commits |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `jablib/.../preferences/JabRefCliPreferences.java` | **2,246** | 302 | **104** | 1 | 218 | 12 | **119** |
| `jabgui/.../gui/LibraryTab.java` | **1,217** | 188 | **102** | 3 | 137 | 21 | **65** |
| `jabgui/.../preferences/JabRefGuiPreferences.java` | **1,130** | 126 | 46 | 2 | 118 | 10 | **69** |
| `jablib/.../fileformat/MedlineImporter.java` | **1,109** | **341** | 19 | 2 | **504** | **86** | 13 |
| `jablib/.../fileformat/BibtexParser.java` | 967 | 259 | 36 | 4 | 296 | 26 | 32 |
| `jabgui/.../openoffice/OOBibBase.java` | 958 | 132 | 34 | 1 | 139 | 15 | 33 |
| `jablib/.../citationkeypattern/BracketedPattern.java` | 916 | 255 | 17 | 1 | **375** | 19 | 19 |
| `jabgui/.../citationrelationtab/CitationRelationsTab.java` | 911 | 106 | 71 | 2 | 96 | 14 | **53** |
| `jablib/.../shared/DBMSSynchronizer.java` | 871 | 174 | 47 | 1 | 169 | 8 | 13 |
| `jabgui/.../frame/JabRefFrame.java` | 833 | 98 | 78 | **6** | 114 | 11 | **63** |

#### Top 5 Files by Cognitive Complexity (Sum / Peak Method)
1. `MedlineImporter.java`: sum **`504`**, max method `45`, Cyclomatic class total `339`
2. `BracketedPattern.java`: sum **`375`**, max method `124`, Cyclomatic class total `255`
3. `RisImporter.java`: sum **`304`**, max method **`304`** (single monolithic method!)
4. `BibtexParser.java`: sum **`296`**, max method `29`, Cyclomatic class total `263`
5. `ModsImporter.java`: sum **`281`**, max method `39`, Cyclomatic class total `216`

---

### 1.3 Code Smells & Duplication (`PMD` 7.29.0 + `PMD CPD`)
*(Scanned `2,298` main Java files; `3,007` violations detected across 18 design & dead-code rules.)*

| Code Smell / Rule | Count | Category |
| :--- | ---: | :--- |
| `LawOfDemeter` | 896 | Coupling / Feature Envy indicator |
| `CyclomaticComplexity` | 377 | High Complexity |
| `CognitiveComplexity` | 297 | High Cognitive Load |
| `TooManyMethods` | 245 | Bloat / SRP Violation |
| `AvoidDeeplyNestedIfStmts` | 241 | Deep Nesting / Readability |
| `ExcessiveImports` | 204 | High Efferent Coupling |
| `CouplingBetweenObjects` | 141 | High CBO (>20) |
| `UnusedPrivateMethod` | 109 | Dead Code |
| **`GodClass`** | **108** | **Architecture / Blob** |
| `NPathComplexity` | 76 | Path Explosion |
| `UnusedFormalParameter` | 71 | Dead Code |
| `UnusedPrivateField` | 63 | Dead Code |
| `NcssCount` | 46 | Long Method / Huge Class |
| `DataClass` | 43 | Anemic Domain / Data Class |
| `ExcessiveParameterList` | 43 | Long Parameter List |
| `ExcessivePublicCount` | 20 | Bloated Public API |
| `TooManyFields` | 18 | State Bloat |
| `UnusedLocalVariable` | 9 | Dead Code |

- **Top Smell-Dense Files:** `BstFunctions.java` (`115` smells, incl. `66` `LawOfDemeter`), `MedlineImporter.java` (`86`, incl. `GodClass` + `14` `CognitiveComplexity`), `ModsImporter.java` (`73`, incl. `GodClass`), `MSBibConverter.java` (`36`), `InMemoryChatHistoryCache.java` (`32`, incl. `GodClass`), `CffImporter.java` (`32`), `BibtexParser.java` (`26`, incl. `GodClass`).
- **Code Duplication (`PMD CPD`, minimum 100 tokens):** **`28` clone groups** across main Java sources:
  - Largest clone: `AllFieldsTab.java` <-> `CitationEntryReviewDialog.java` (`47` lines, `251` tokens)
  - Second largest: `PanelStep.java` <-> `TooltipStep.java` (`52` lines, `212` tokens + second `44`-line/`154`-token clone!)
  - `ChatHistoryMigrationV1.java` <-> `SummariesMigrationV1.java` (`39` lines, `178` tokens)
  - `GetCitedWorks.java` <-> `GetCitingWorks.java` (`49` lines, `161` tokens)

---

### 1.4 Repository Evolution (`PyDriller` 2.12 — 24-Month Window)
*(Window: `2024-11-18` to `2026-11-18`, ending at baseline `454ee66398`; `4,330` non-merge commits analyzed.)*

- **Contributor Activity:** `376` distinct authors over 24 months; `140` active in the last 6 months (`>= 2026-05-20`).
- **Scope Touched:** `4,732` baseline files modified (`3,289` Java files; all `2,311` production Java files had >=1 commit in the 24m window).
- **Top Churn Production Files (24m / 12m commits):**
  1. `JabRefCliPreferences.java`: **`119`** (24m) / **`79`** (12m), `47` authors (main share `20.2%`)
  2. `JabRefGuiPreferences.java`: **`69`** (24m) / **`52`** (12m), `34` authors (`20.3%`)
  3. `JabRefGUI.java`: **`68`** (24m) / **`41`** (12m), `22` authors (`30.9%`)
  4. `LibraryTab.java`: **`65`** (24m) / **`47`** (12m), `19` authors (`30.8%`)
  5. `JabRefFrame.java`: **`63`** (24m) / **`35`** (12m), `31` authors (`27.0%`)
  6. `jablib/src/main/java/module-info.java`: **`62`** (24m) / **`35`** (12m), `24` authors
  7. `StandardActions.java`: **`54`** (24m) / **`28`** (12m), `34` authors
  8. `CitationRelationsTab.java`: **`53`** (24m) / **`38`** (12m), `31` authors
- **Ownership & Bus Factor Signals (24m):**
  - Median distinct authors per main Java file: `2.0` (max `47` in `JabRefCliPreferences.java`).
  - **`751`** main Java files have `Bus Factor = 1` (single distinct author in 24m); **`791`** have main author share `>= 80%`.
  - **`156`** main Java files have a main author who has been **inactive for the last 6 months** (notably the `walkthrough/` subsystem authored primarily by `Yubo Cao`, including `PanelStep.java` and `TooltipStep.java` which also contain duplicated clones).
- **Temporal Coupling Signals:** `311` Java file pairs with `>= 5` shared commits (excluding `57` bulk commits touching `> 30` Java files). Strongest pairs already exceeding `70%` co-change include:
  - `JournalListMvGenerator.java` <-> `LtwaListMvGenerator.java` (`22` shared commits, `84.6%` / `71.0%`)
  - `OcrTabViewModel.java` <-> `OcrPreferences.java` (`5` shared, `71.4%` / `83.3%`)
  - `OcrTab.java` <-> `OcrTabViewModel.java` (`5` shared, `83.3%` / `71.4%`)
  - `Convert.java` <-> `GenerateBibFromAux.java` (`7` shared, `53.8%` / `77.8%`)
  - `jabsrv-cli/module-info.java` <-> `jabsrv/module-info.java` (`11` shared, `100%` of `jabsrv-cli` commits)

### Stage 1 Artifacts (`PROGRESS/stage1/`)
- `scc_summary.txt`, `scc_summary.json`, `scc_java_files.csv`
- `ck_class_metrics.csv`, `ck_file_metrics.csv`
- `pmd_smells_main.csv`, `pmd_file_smells.csv`, `pmd-smells-ruleset.xml`
- `pmd_complexity_main.csv`, `pmd_file_complexity.csv`, `pmd-metrics-ruleset.xml`
- `pmd_cpd_main.csv`
- `git_file_evolution_24m.csv`, `git_temporal_coupling_24m.csv`, `git_author_activity_24m.csv`, `git_evolution_meta.json`
- `stage1_master_java_metrics.csv`, `stage1_summary_stats.json`
- Scripts: `mine_git_history.py`, `build_stage1_metrics.py`

---

## Stage 2: Data Correlation & Hotspot Analysis

*Status: Pending — ready to execute using `PROGRESS/stage1/stage1_master_java_metrics.csv` and `git_temporal_coupling_24m.csv`.*

---

## Stage 3: Root Cause Analysis & Refactoring Plan

*Status: Pending*
