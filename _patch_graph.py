from pathlib import Path

path = Path('app/api/routes/graph.py')
text = path.read_text(encoding='utf-8')
old = "    if search:\r\n        like = f\"%{search.lower()}%\"\r\n        query = query.where(Node.label.ilike(like) | Node.summary.ilike(like))\r\n"
new = "    if search:\r\n        term = str(search).strip().lower()\r\n        if term:\r\n            like = f\"%{term}%\"\r\n            query = query.where(Node.label.ilike(like) | Node.summary.ilike(like))\r\n"
if old not in text:
    raise SystemExit('pattern not found in graph.py')
text = text.replace(old, new)
path.write_text(text, encoding='utf-8')
