import pathlib

exts = {".py", ".html", ".json", ".txt", ".md"}
skip_dirs = {"venv", "__pycache__", "migrations", ".git"}

root = pathlib.Path(".")
parts = []

for f in sorted(root.rglob("*")):
    if any(s in f.parts for s in skip_dirs):
        continue
    if f.suffix not in exts:
        continue
    if f.stat().st_size > 30000:
        continue

    parts.append(f"### {f}\n{f.read_text(errors='ignore')}")

pathlib.Path("context.txt").write_text("\n\n".join(parts), encoding="utf-8")
print("Written to context.txt")