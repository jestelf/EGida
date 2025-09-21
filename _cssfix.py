from pathlib import Path

text = Path("app/static/css/main.css").read_text(encoding="utf-8")
block = "\n.secondary.is-active {\n  border-color: var(--accent);\n  color: var(--accent);\n}\n\n.layout-toggle {\n  flex-wrap: wrap;\n}\n\n"
parts = text.split(block)
print(len(parts))
