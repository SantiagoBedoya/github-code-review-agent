from __future__ import annotations

from github_code_review.config import settings

VALID_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".cpp",
    ".c",
    ".rs",
    ".swift",
    ".kt",
    ".md",
}

EXCLUDED_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Gemfile.lock",
    ".env.example",
}


def is_valid_file(filename: str, status: str, additions: int, deletions: int) -> bool:
    if filename in EXCLUDED_FILES:
        return False
    ext = "." + filename.rsplit(".", 1)[-1]
    if ext not in VALID_EXTENSIONS:
        return False
    if status == "removed":
        return False
    if additions + deletions > settings.max_changed_lines:
        return False
    return True
