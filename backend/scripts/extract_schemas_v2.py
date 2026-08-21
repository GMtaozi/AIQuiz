#!/usr/bin/env python3
"""
Remove inline BaseModel schemas from router files and add proper imports.
Uses AST to reliably identify and remove class definitions.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"
SCHEMAS_DIR = APP_DIR / "schemas"

ROUTERS = [
    "routers/audit.py",
    "routers/auth.py",
    "routers/dashboard.py",
    "routers/exam_records.py",
    "routers/exams.py",
    "routers/knowledge.py",
    "routers/notifications.py",
    "routers/paper_template.py",
    "routers/papers.py",
]

# Map router file to schema module
ROUTER_TO_SCHEMA = {
    "routers/audit.py": "app.schemas.audit",
    "routers/auth.py": "app.schemas.auth",
    "routers/dashboard.py": "app.schemas.dashboard",
    "routers/exam_records.py": "app.schemas.exam_record",
    "routers/exams.py": "app.schemas.exam",
    "routers/knowledge.py": "app.schemas.knowledge",
    "routers/notifications.py": "app.schemas.notification",
    "routers/paper_template.py": "app.schemas.paper_template",
    "routers/papers.py": "app.schemas.paper",
}


def find_basemodel_classes(content: str) -> list[tuple[int, int]]:
    """Find line ranges of BaseModel classes using AST."""
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


def remove_lines(content: str, lines_to_remove: set[int]) -> str:
    """Remove specified lines (1-indexed) from content."""
    result = []
    for i, line in enumerate(content.split("\n"), 1):
        if i not in lines_to_remove:
            result.append(line)
    return "\n".join(result)


def clean_imports(content: str) -> str:
    """Remove unused pydantic imports."""
    lines = content.split("\n")
    result = []

    # Track which pydantic items are still used
    pydantic_items = {"BaseModel", "ConfigDict", "Field", "field_validator", "EmailStr"}

    # First pass: check usage
    used_items = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            continue
        for item in pydantic_items:
            if item in line:
                used_items.add(item)

    # Second pass: filter imports
    for line in lines:
        stripped = line.strip()

        # Remove unused pydantic imports
        if "from pydantic import" in line:
            items_in_line = []
            # Parse what's being imported
            import_part = line.split("import")[1].strip()
            # Handle multi-line imports
            items = [x.strip() for x in import_part.split(",")]
            kept = [item for item in items if item.split(" as ")[0].strip() in used_items]
            if kept:
                result.append(f"from pydantic import {', '.join(kept)}")
            continue

        # Remove pydantic.BaseModel import if unused
        if stripped == "from pydantic import BaseModel" and "BaseModel" not in used_items:
            continue
        if stripped == "from pydantic import ConfigDict" and "ConfigDict" not in used_items:
            continue
        if stripped == "from pydantic import Field" and "Field" not in used_items:
            continue
        if stripped == "from pydantic import field_validator" and "field_validator" not in used_items:
            continue

        result.append(line)

    return "\n".join(result)


def clean_blank_lines(content: str) -> str:
    """Remove excessive blank lines."""
    lines = content.split("\n")
    result = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:  # Allow max 2 consecutive blank lines
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    return "\n".join(result)


def process_router(rel_path: str) -> None:
    """Process a single router file."""
    filepath = APP_DIR / rel_path
    if not filepath.exists():
        print(f"⚠ {filepath} not found")
        return

    content = filepath.read_text(encoding="utf-8")

    # Find BaseModel class ranges
    ranges = find_basemodel_classes(content)
    if not ranges:
        print(f"  ⊘ {rel_path} - no BaseModel classes found")
        return

    # Mark lines to remove
    lines_to_remove = set()
    for start, end in ranges:
        for i in range(start, end + 1):
            lines_to_remove.add(i)

    # Also remove schema section headers
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("# ============ Schema") or stripped.startswith("# ============ Pydantic"):
            lines_to_remove.add(i)
            # Remove blank lines after header
            for j in range(i + 1, len(lines) + 1):
                if j <= len(lines) and lines[j - 1].strip() == "":
                    lines_to_remove.add(j)
                else:
                    break

    # Remove lines
    updated = remove_lines(content, lines_to_remove)

    # Clean imports
    updated = clean_imports(updated)

    # Clean blank lines
    updated = clean_blank_lines(updated)

    # Add schema import
    schema_module = ROUTER_TO_SCHEMA.get(rel_path)
    if schema_module:
        import_line = f"from {schema_module} import *"
        if import_line not in updated:
            # Insert after existing app imports
            lines = updated.split("\n")
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("from app.") or line.strip().startswith("import "):
                    insert_idx = i + 1
                elif line.strip().startswith("logger") or line.strip().startswith("router ="):
                    break
            lines.insert(insert_idx, import_line)
            updated = "\n".join(lines)

    filepath.write_text(updated, encoding="utf-8")
    print(f"  ✓ {rel_path} (removed {len(lines_to_remove)} lines)")


def main() -> None:
    for rel_path in ROUTERS:
        process_router(rel_path)

    print("\n✓ Schema extraction complete!")


if __name__ == "__main__":
    main()
