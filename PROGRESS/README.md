# PROGRESS — Maintainability Audit Outputs

This directory stores all raw data, analysis scripts, intermediate artifacts, visualizations, and final report files for the **System Maintainability Audit & Refactoring Plan** on `JabRef/jabref`.

## Planned Structure

- `stage1/` — Raw metrics exports (`scc`, `CK`, `PMD`, `PMD CPD`, `PyDriller` CSV/JSON outputs)
- `stage2/` — Correlated datasets (Hotspot matrix, Logical Coupling pairs, Bus Factor / Knowledge Loss analysis)
- `stage3/` — Deep-dive Root Cause Analysis notes and refactoring proposals
- `charts/` — Visualizations (Complexity vs. Change Frequency hotspot matrix, Code Smell distribution, etc.)
- `report/` — Final Audit Report (`AUDIT_REPORT.md` / exported deliverables)
