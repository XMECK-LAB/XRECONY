from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


def build_intelligence(generation_dir: Path) -> dict:
    """Produce explainable metadata-only observations; never infer file content."""
    conn = sqlite3.connect(generation_dir / "records.sqlite3")
    conn.row_factory = sqlite3.Row
    try:
        duplicate_groups = []
        for row in conn.execute(
            """
            SELECT size, extension, COUNT(*) AS count,
                   GROUP_CONCAT(rel_path, char(10)) AS paths
            FROM records
            WHERE kind='file' AND size > 0
            GROUP BY size, extension
            HAVING COUNT(*) > 1
            ORDER BY count DESC, size DESC
            LIMIT 250
            """
        ):
            paths = row["paths"].splitlines()
            duplicate_groups.append(
                {
                    "basis": "same logical size and extension; content is not hashed",
                    "size": row["size"],
                    "extension": row["extension"],
                    "count": row["count"],
                    "paths": paths,
                }
            )
        families: dict[str, list[str]] = {}
        for row in conn.execute("SELECT name, rel_path FROM records WHERE kind='file'"):
            stem = Path(row["name"]).stem.lower()
            normalized = "".join("#" if c.isdigit() else c for c in stem)
            normalized = " ".join(normalized.replace("_", " ").replace("-", " ").split())
            if len(normalized) >= 4:
                families.setdefault(normalized, []).append(row["rel_path"])
        version_families = [
            {"signature": key, "count": len(paths), "paths": paths[:50]}
            for key, paths in families.items()
            if len(paths) > 1
        ]
        version_families.sort(key=lambda item: (-item["count"], item["signature"]))
        categories = dict(conn.execute("SELECT category, COUNT(*) FROM records GROUP BY category"))
        years = dict(conn.execute("SELECT year, COUNT(*) FROM records GROUP BY year"))
        extensions = Counter(
            row[0] or "[none]"
            for row in conn.execute("SELECT extension FROM records WHERE kind='file'")
        )
        empty_folders = [
            row[0]
            for row in conn.execute(
                """
                SELECT d.rel_path FROM records d
                LEFT JOIN records c ON c.parent_id=d.record_id
                WHERE d.kind='directory'
                GROUP BY d.record_id
                HAVING COUNT(c.record_id)=0
                ORDER BY d.rel_path
                LIMIT 500
                """
            )
        ]
        largest = [
            {"path": row["rel_path"], "size": row["size"], "category": row["category"]}
            for row in conn.execute(
                "SELECT rel_path,size,category FROM records WHERE kind='file' ORDER BY size DESC LIMIT 100"
            )
        ]
    finally:
        conn.close()
    return {
        "format": "xrecony-metadata-intelligence-v3-candidate",
        "evidence_boundary": "Metadata-only observations; duplicate candidates are not content-confirmed duplicates.",
        "summary": {
            "duplicate_candidate_groups": len(duplicate_groups),
            "version_family_candidates": len(version_families),
            "empty_folders": len(empty_folders),
            "categories": len(categories),
        },
        "duplicate_candidates": duplicate_groups,
        "version_families": version_families[:250],
        "empty_folders": empty_folders,
        "largest_files": largest,
        "category_distribution": categories,
        "year_distribution": years,
        "top_extensions": extensions.most_common(30),
    }


def write_intelligence(generation_dir: Path) -> dict:
    result = build_intelligence(generation_dir)
    (generation_dir / "intelligence.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    return result
