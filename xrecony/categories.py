from __future__ import annotations

from pathlib import Path


CATEGORIES = {
    "documents": {".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pdf"},
    "spreadsheets": {".xls", ".xlsx", ".ods", ".csv", ".tsv"},
    "presentations": {".ppt", ".pptx", ".odp"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".svg"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"},
    "archives": {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2"},
    "code": {".py", ".rs", ".go", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".c", ".cpp", ".h", ".cs", ".html", ".css", ".json", ".yaml", ".yml", ".toml"},
    "executables": {".exe", ".msi", ".apk", ".appx", ".dll", ".so", ".dylib"},
}


def classify(name: str, is_dir: bool) -> tuple[str, str]:
    if is_dir:
        return "folders", ""
    ext = Path(name).suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category, ext
    return ("other" if ext else "untyped"), ext
