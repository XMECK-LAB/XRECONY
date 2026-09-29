from __future__ import annotations

import sqlite3
from pathlib import Path


def query_records(generation_dir: Path, query: str = "", category: str = "", kind: str = "", view: str = "source", page: int = 1, page_size: int = 100) -> dict:
    page = max(1, page)
    page_size = min(500, max(10, page_size))
    clauses = []
    params: list[object] = []
    if query:
        clauses.append("(name LIKE ? OR rel_path LIKE ?)")
        token = f"%{query}%"
        params.extend((token, token))
    if category:
        clauses.append("category = ?")
        params.append(category)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    path_column = {
        "type": "type_path",
        "timeline": "time_path",
        "recovery": "CASE WHEN status='placed' THEN 'Recovery/Stable/' || rel_path ELSE 'Recovery/Attention/' || rel_path END",
    }.get(view, "rel_path")
    conn = sqlite3.connect(generation_dir / "records.sqlite3")
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM records{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT record_id,name,rel_path,{path_column} AS view_path,kind,size,category,extension,year,status,error FROM records{where} ORDER BY view_path COLLATE NOCASE LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
        categories = [dict(row) for row in conn.execute("SELECT category AS name, COUNT(*) AS count FROM records GROUP BY category ORDER BY count DESC")]
        years = [dict(row) for row in conn.execute("SELECT year AS name, COUNT(*) AS count FROM records GROUP BY year ORDER BY year DESC")]
    finally:
        conn.close()
    records = []
    for row in rows:
        item = dict(row)
        item.update(
            {
                "id": item["record_id"],
                "path": item["rel_path"],
                "reconstructed_path": item["view_path"],
                "logical_size": item["size"],
                "modified_year": item["year"],
                "state": item["status"],
            }
        )
        records.append(item)
    facets = {item["name"]: item["count"] for item in categories}
    pages = max(1, (total + page_size - 1) // page_size)
    return {"records": records, "total": total, "page": page, "pages": pages, "page_size": page_size, "categories": categories, "facets": facets, "years": years, "view": view}


def record_detail(generation_dir: Path, record_id: str) -> dict | None:
    conn = sqlite3.connect(generation_dir / "records.sqlite3")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM records WHERE record_id = ?", (record_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
