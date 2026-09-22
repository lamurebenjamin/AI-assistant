"""Check source module sizes while allowing documented orchestration modules."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (ROOT / "src", ROOT / "core", ROOT / "skills")
MAX_LINES = 500
ALLOWED_LARGE_MODULES = {
    "src/ui/windows/document_dialog.py": 1800,
    "src/ui/windows/document_conversation_renderer.py": 550,
    "src/ui/windows/assistant_window.py": 1600,
    "src/ui/windows/settings_dialog.py": 800,
    "src/ui/stylesheet.py": 700,
    "src/ui/widgets/tool_call_widget.py": 700,
}

violations = []
for source_root in SOURCE_ROOTS:
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        lines = len(path.read_text(encoding="utf-8").splitlines())
        limit = ALLOWED_LARGE_MODULES.get(relative, MAX_LINES)
        if lines > limit:
            violations.append(f"{relative}: {lines} lines (limit {limit})")

if violations:
    print("Module size violations:")
    print("\n".join(sorted(violations)))
    sys.exit(1)

print(f"Module size check passed ({MAX_LINES}-line default threshold).")
