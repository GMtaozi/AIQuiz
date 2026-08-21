#!/usr/bin/env python3
"""
Clean up router files after schema extraction:
1. Remove orphaned BaseModel class remnants
2. Remove unused pydantic imports
3. Clean up blank lines
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"

ROUTERS_TO_CLEAN = [
    "audit.py",
    "auth.py",
    "dashboard.py",
    "exam_records.py",
    "exams.py",
    "knowledge.py",
    "notifications.py",
    "paper_template.py",
    "papers.py",
]


def find_basemodel_ranges(content: str) -> list[tuple[int, int]]:
    """Find line ranges (1-indexed) of all BaseModel classes."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    ranges = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if "BaseModel" in bases:
                start = node.lineno  # 1-indexed
                end = getattr(node, "end_lineno", start)
                ranges.append((start, end))

    return ranges


def clean_router(filepath: Path) -> None:
    """Remove BaseModel class blocks and clean up imports."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Find BaseModel class ranges
    ranges = find_basemodel_ranges(content)
    if not ranges:
        return

    # Mark lines to remove (1-indexed)
    remove_lines = set()
    for start, end in ranges:
        for i in range(start, end + 1):
            remove_lines.add(i)

    # Also remove schema section headers
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("# ============ Schema") or stripped.startswith("# ============ Pydantic"):
            # Remove this header line
            remove_lines.add(i)
            # Also remove blank lines after it
            for j in range(i + 1, len(lines) + 1):
                if j <= len(lines) and lines[j - 1].strip() == "":
                    remove_lines.add(j)
                else:
                    break

    # Build cleaned content
    cleaned = []
    for i, line in enumerate(lines, 1):
        if i not in remove_lines:
            cleaned.append(line)

    # Remove multiple consecutive blank lines
    result = []
    prev_blank = False
    for line in cleaned:
        if line.strip() == "":
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    # Remove unused pydantic imports if no BaseModel/Field/field_validator/ConfigDict usage remains
    final_lines = result[:]
    pydantic_imports_to_check = [
        "from pydantic import BaseModel",
        "from pydantic import ConfigDict",
        "from pydantic import Field",
        "from pydantic import field_validator",
        "from pydantic import EmailStr",
    ]

    for imp in pydantic_imports_to_check:
        # Check if this import is still used in non-import lines
        still_used = False
        for line in final_lines:
            stripped = line.strip()
            if stripped.startswith("from ") or stripped.startswith("import "):
                continue
            if imp.split("import ")[1].split(",")[0].strip() in line:
                still_used = True
                break

        if not still_used:
            # Remove the import line
            final_lines = [line for line in final_lines if imp not in line]

    # Write back
    filepath.write_text("\n".join(final_lines), encoding="utf-8")
    print(f"  ✓ Cleaned {filepath.name} (removed {len(remove_lines)} lines)")


def main() -> None:
    routers_dir = APP_DIR / "routers"
    for rel_path in ROUTERS_TO_CLEAN:
        filepath = routers_dir / rel_path
        if not filepath.exists():
            print(f"⚠ {filepath} not found")
            continue
        clean_router(filepath)

    print("\n✓ Router cleanup complete!")


if __name__ == "__main__":
    main()
