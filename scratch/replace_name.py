import os
import re

ROOT_DIR = "/Users/johnwesleygovada/Desktop/Safar"

EXCLUDE_DIRS = {
    ".git",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
    "build",
    "__pycache__",
    ".dart_tool"
}

EXCLUDE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".7z", ".pyc", ".db", ".sqlite", ".sqlite3"
}

REPLACEMENTS = [
    (re.compile(r"Safar\s+Balm", re.IGNORECASE), "Safar"),
    (re.compile(r"Safar"), "Safar"),
    (re.compile(r"Safar"), "Safar"),
    (re.compile(r"safar"), "safar"),
    (re.compile(r"SAFAR"), "SAFAR"),
    (re.compile(r"Safar"), "Safar"),
    (re.compile(r"safar"), "safar"),
    (re.compile(r"SAFAR"), "SAFAR"),
]

def replace_in_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False, 0

    original = content
    changes_count = 0
    for pattern, replacement in REPLACEMENTS:
        matches = len(pattern.findall(content))
        if matches > 0:
            content = pattern.sub(replacement, content)
            changes_count += matches

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True, changes_count
    return False, 0

def main():
    modified_files = []
    total_replacements = 0

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue

            filepath = os.path.join(root, file)
            modified, count = replace_in_file(filepath)
            if modified:
                relative_path = os.path.relpath(filepath, ROOT_DIR)
                modified_files.append((relative_path, count))
                total_replacements += count

    print(f"\n--- RENAMING COMPLETED ---")
    print(f"Total files modified: {len(modified_files)}")
    print(f"Total occurrences replaced: {total_replacements}\n")
    for path, count in modified_files:
        print(f" - {path} ({count} replacements)")

if __name__ == "__main__":
    main()
