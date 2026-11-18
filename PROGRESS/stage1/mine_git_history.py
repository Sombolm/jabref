"""Mine 24-month Git commit history of JabRef using PyDriller.

Outputs (saved in PROGRESS/stage1/):
- git_file_evolution_24m.csv: Churn (commits, lines added/deleted), 12m churn, ownership, bus factor signals
- git_temporal_coupling_24m.csv: Co-change pairs (>= 5 shared commits) for logical coupling analysis
- git_author_activity_24m.csv: Author commit counts, first/last commit dates (active vs inactive check)
- git_evolution_meta.json: Summary statistics for the mined commit window
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

from pydriller import Repository

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
BASELINE_COMMIT = "454ee663981cf6c51b5fc3f190fb0ed0fcdf799b"
MAX_FILES_PER_COMMIT_FOR_COUPLING = 30
MIN_SHARED_COMMITS = 5


def get_existing_files_at_baseline(commit_sha: str) -> set[str]:
    res = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit_sha],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.strip().replace("\\", "/") for line in res.stdout.splitlines() if line.strip()}


def normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    return path.replace("\\", "/")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = get_existing_files_at_baseline(BASELINE_COMMIT)

    # Anchor dates relative to baseline commit timestamp (2026-11-18T15:19:13Z)
    baseline_dt = datetime(2026, 11, 18, 15, 19, 13, tzinfo=timezone.utc)
    since_24m = baseline_dt - timedelta(days=730)
    since_12m = baseline_dt - timedelta(days=365)
    since_6m = baseline_dt - timedelta(days=182)

    file_commits_24m: Counter[str] = Counter()
    file_commits_12m: Counter[str] = Counter()
    file_added_24m: Counter[str] = Counter()
    file_deleted_24m: Counter[str] = Counter()
    file_authors: dict[str, Counter[str]] = defaultdict(Counter)
    file_last_modified: dict[str, datetime] = {}

    author_commits: Counter[str] = Counter()
    author_names: dict[str, str] = {}
    author_first_commit: dict[str, datetime] = {}
    author_last_commit: dict[str, datetime] = {}

    pair_counts: Counter[tuple[str, str]] = Counter()
    coupling_file_commits: Counter[str] = Counter()

    total_commits = 0
    skipped_bulk_coupling = 0
    rename_map: dict[str, str] = {}

    print(f"Mining commits from {since_24m.isoformat()} to {BASELINE_COMMIT}...")
    repo = Repository(
        str(REPO_ROOT),
        since=since_24m,
        to_commit=BASELINE_COMMIT,
        only_no_merge=True,
        order="reverse",
    )

    for commit in repo.traverse_commits():
        total_commits += 1
        if total_commits % 250 == 0:
            print(f"  processed {total_commits} commits...", flush=True)

        c_dt = commit.committer_date.astimezone(timezone.utc)
        author_key = (commit.author.email or commit.author.name or "unknown").strip().lower()
        author_name = (commit.author.name or author_key).strip()

        author_commits[author_key] += 1
        author_names[author_key] = author_name
        if author_key not in author_first_commit or c_dt < author_first_commit[author_key]:
            author_first_commit[author_key] = c_dt
        if author_key not in author_last_commit or c_dt > author_last_commit[author_key]:
            author_last_commit[author_key] = c_dt

        touched_in_commit: set[str] = set()
        for mod in commit.modified_files:
            new_p = normalize_path(mod.new_path)
            old_p = normalize_path(mod.old_path)

            # Resolve historical renames forward to baseline path when traversing newest->oldest
            if new_p and old_p and new_p != old_p:
                target = rename_map.get(new_p, new_p)
                rename_map[old_p] = target

            raw_path = new_p or old_p
            if not raw_path:
                continue
            resolved_path = rename_map.get(raw_path, raw_path)

            file_commits_24m[resolved_path] += 1
            if c_dt >= since_12m:
                file_commits_12m[resolved_path] += 1
            file_added_24m[resolved_path] += mod.added_lines
            file_deleted_24m[resolved_path] += mod.deleted_lines
            file_authors[resolved_path][author_key] += 1

            if resolved_path not in file_last_modified or c_dt > file_last_modified[resolved_path]:
                file_last_modified[resolved_path] = c_dt

            if resolved_path.endswith(".java") and resolved_path in existing_files:
                touched_in_commit.add(resolved_path)

        if 2 <= len(touched_in_commit) <= MAX_FILES_PER_COMMIT_FOR_COUPLING:
            for f in touched_in_commit:
                coupling_file_commits[f] += 1
            for a, b in combinations(sorted(touched_in_commit), 2):
                pair_counts[(a, b)] += 1
        elif len(touched_in_commit) > MAX_FILES_PER_COMMIT_FOR_COUPLING:
            skipped_bulk_coupling += 1

    print(f"Finished mining {total_commits} non-merge commits.")

    # Write author activity
    author_rows = []
    for a_key, cnt in author_commits.most_common():
        last_dt = author_last_commit[a_key]
        is_active_6m = last_dt >= since_6m
        author_rows.append(
            {
                "author_email": a_key,
                "author_name": author_names[a_key],
                "commits_24m": cnt,
                "first_commit_24m": author_first_commit[a_key].isoformat(),
                "last_commit_24m": last_dt.isoformat(),
                "active_last_6m": is_active_6m,
            }
        )

    with (OUT_DIR / "git_author_activity_24m.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(author_rows[0].keys()))
        writer.writeheader()
        writer.writerows(author_rows)

    # Write file evolution metrics (only files existing at baseline)
    evo_rows = []
    for path in sorted(existing_files):
        commits_24 = file_commits_24m.get(path, 0)
        if commits_24 == 0:
            continue
        authors_counter = file_authors[path]
        main_author, main_author_commits = authors_counter.most_common(1)[0]
        main_share = main_author_commits / commits_24
        main_author_last = author_last_commit[main_author]
        evo_rows.append(
            {
                "file_path": path,
                "is_java": path.endswith(".java"),
                "is_test": "/src/test/" in path,
                "commits_24m": commits_24,
                "commits_12m": file_commits_12m.get(path, 0),
                "lines_added_24m": file_added_24m.get(path, 0),
                "lines_deleted_24m": file_deleted_24m.get(path, 0),
                "total_churn_lines_24m": file_added_24m.get(path, 0) + file_deleted_24m.get(path, 0),
                "distinct_authors_24m": len(authors_counter),
                "main_author_email": main_author,
                "main_author_name": author_names[main_author],
                "main_author_commits": main_author_commits,
                "main_author_share": round(main_share, 4),
                "main_author_last_commit": main_author_last.isoformat(),
                "main_author_active_6m": main_author_last >= since_6m,
                "file_last_modified": file_last_modified[path].isoformat(),
            }
        )

    evo_rows.sort(key=lambda r: r["commits_24m"], reverse=True)
    with (OUT_DIR / "git_file_evolution_24m.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(evo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(evo_rows)

    # Write temporal coupling pairs
    coupling_rows = []
    for (fa, fb), shared in pair_counts.items():
        if shared < MIN_SHARED_COMMITS:
            continue
        ca = file_commits_24m[fa]
        cb = file_commits_24m[fb]
        conf_a = shared / ca if ca else 0.0
        conf_b = shared / cb if cb else 0.0
        union = ca + cb - shared
        jaccard = shared / union if union else 0.0
        coupling_rows.append(
            {
                "file_a": fa,
                "file_b": fb,
                "shared_commits": shared,
                "commits_a": ca,
                "commits_b": cb,
                "confidence_a_to_b": round(conf_a, 4),
                "confidence_b_to_a": round(conf_b, 4),
                "max_confidence": round(max(conf_a, conf_b), 4),
                "avg_confidence": round((conf_a + conf_b) / 2.0, 4),
                "jaccard_similarity": round(jaccard, 4),
            }
        )

    coupling_rows.sort(key=lambda r: (r["shared_commits"], r["max_confidence"]), reverse=True)
    with (OUT_DIR / "git_temporal_coupling_24m.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "file_a",
            "file_b",
            "shared_commits",
            "commits_a",
            "commits_b",
            "confidence_a_to_b",
            "confidence_b_to_a",
            "max_confidence",
            "avg_confidence",
            "jaccard_similarity",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(coupling_rows)

    meta = {
        "baseline_commit": BASELINE_COMMIT,
        "since_24m": since_24m.isoformat(),
        "since_12m": since_12m.isoformat(),
        "since_6m_active_cutoff": since_6m.isoformat(),
        "non_merge_commits_analyzed": total_commits,
        "distinct_authors_24m": len(author_commits),
        "active_authors_6m": sum(1 for dt in author_last_commit.values() if dt >= since_6m),
        "baseline_files_modified_in_24m": len(evo_rows),
        "baseline_java_files_modified_in_24m": sum(1 for r in evo_rows if r["is_java"]),
        "coupling_max_files_per_commit": MAX_FILES_PER_COMMIT_FOR_COUPLING,
        "skipped_bulk_commits_for_coupling": skipped_bulk_coupling,
        "coupling_pairs_min_shared_5": len(coupling_rows),
    }
    with (OUT_DIR / "git_evolution_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("Saved evolution outputs:", json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
