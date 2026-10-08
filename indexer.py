"""indexer.py: stdlib-only code graph in graphify's graph.json shape (nodes + calls links).
Usage: python indexer.py [repo] [--out graph.json]
"""
import ast, hashlib, json, os, pathlib, re, sys, tempfile
from collections import defaultdict

SKIP_DIRS = {".git", "node_modules", "graphify-out", "dist", "build", "target", "venv", ".venv", "__pycache__", ".next"}
MAX_BYTES = 500_000
JS = [r"\bfunction\s*\*?\s*(\w+)", r"\bclass\s+(\w+)", r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>",
      r"^\s*(?:export\s+)?(?:static\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[\w<>\[\]| ]+)?\s*\{"]
C_LIKE = [r"\b(?:class|interface|enum|struct)\s+(\w+)", r"^\s*(?:[\w<>\[\],:*&]+\s+)+(\w+)\s*\([^;)]*\)\s*(?:const|throws[\w\s,.]+)?\s*\{"]
PATTERNS = {
    ".js": JS, ".jsx": JS, ".ts": JS, ".tsx": JS, ".vue": JS, ".svelte": JS,
    ".rs": [r"\bfn\s+(\w+)", r"\b(?:struct|enum|trait)\s+(\w+)"],
    ".go": [r"\bfunc\s+(?:\([^)]*\)\s*)?(\w+)", r"\btype\s+(\w+)\s+(?:struct|interface)"],
    ".rb": [r"\bdef\s+(?:self\.)?(\w+)", r"\b(?:class|module)\s+(\w+)"],
    ".php": [r"\bfunction\s+(\w+)", r"\b(?:class|interface|trait)\s+(\w+)"],
    ".kt": [r"\bfun\s+(?:\w+\.)?(\w+)", r"\b(?:class|interface|object)\s+(\w+)"],
    ".swift": [r"\bfunc\s+(\w+)", r"\b(?:class|struct|enum|protocol)\s+(\w+)"],
    ".java": C_LIKE, ".cs": C_LIKE, ".c": C_LIKE, ".cpp": C_LIKE, ".h": C_LIKE,
}
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
KEYWORDS = set("if for while switch catch return function fn func def class new typeof sizeof await async elif else with "
               "print super this self len str int list dict set tuple range isinstance".split())


def py_defs(src):
    # ast gives exact spans, so calls land in the right function
    tree = ast.parse(src)
    defs = []

    def walk(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                fn = not isinstance(ch, ast.ClassDef)
                defs.append((ch.lineno, ch.end_lineno, ch.name + ("()" if fn else "")))
            walk(ch)
    walk(tree)
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name:
                calls.append((n.lineno, name))
    return defs, calls


def rx_defs(src, pats):
    lines = src.splitlines()
    found = []
    for i, line in enumerate(lines, 1):
        for p in pats:
            m = re.search(p, line)
            if m and m.group(1) not in KEYWORDS:
                found.append((i, m.group(1)))
                break
    # end of a declaration = line before the next one
    defs = [(ln, found[k + 1][0] - 1 if k + 1 < len(found) else len(lines), nm + "()") for k, (ln, nm) in enumerate(found)]
    calls = [(i, m.group(1)) for i, line in enumerate(lines, 1) for m in CALL.finditer(line) if m.group(1) not in KEYWORDS]
    return defs, calls


def sources(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for n in names:
            p = pathlib.Path(d, n)
            if p.suffix == ".py" or p.suffix in PATTERNS:
                yield p


def build_cached(root):
    # parsing is the slow part; reuse the graph while no source file changed
    root = pathlib.Path(root).resolve()
    sig = hashlib.sha1()
    for p in sorted(sources(root)):
        st = p.stat()
        sig.update(f"{p}|{st.st_size}|{st.st_mtime_ns}".encode())
    f = pathlib.Path(tempfile.gettempdir(), "desolator-index", hashlib.sha1(str(root).encode()).hexdigest() + ".json")
    try:
        c = json.loads(f.read_text(encoding="utf8"))
        if c["sig"] == sig.hexdigest():
            return c["graph"]
    except (OSError, ValueError, KeyError):
        pass
    g = build(root)
    try:
        f.parent.mkdir(exist_ok=True)
        f.write_text(json.dumps({"sig": sig.hexdigest(), "graph": g}), encoding="utf8")
    except OSError:
        pass
    return g


def build(root):
    root = pathlib.Path(root).resolve()
    nodes, per_file = [], []
    by_name = defaultdict(list)
    for p in sources(root):
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            src = p.read_text(encoding="utf8", errors="ignore")
            defs, calls = py_defs(src) if p.suffix == ".py" else rx_defs(src, PATTERNS[p.suffix])
        except (SyntaxError, ValueError, OSError):
            continue
        rel = p.relative_to(root).as_posix()
        ids = []
        for ln, end, label in sorted(defs):
            nid = f"{rel}::{label}@{ln}"
            nodes.append({"id": nid, "label": label, "source_file": rel, "source_location": f"L{ln}"})
            ids.append((ln, end, nid))
            by_name[label.rstrip("()")].append(nid)
        per_file.append((ids, calls))
    links, seen = [], set()
    for ids, calls in per_file:
        # innermost declaration = smallest span holding the call
        ids = sorted(ids, key=lambda x: x[1] - x[0])
        for ln, name in calls:
            owner = next((nid for s, e, nid in ids if s <= ln <= e), None)
            tgt = by_name.get(name, [])
            if owner and 0 < len(tgt) <= 3:
                for t in tgt:
                    if t != owner and (owner, t) not in seen:
                        seen.add((owner, t))
                        links.append({"source": owner, "target": t, "relation": "calls"})
    return {"directed": True, "nodes": nodes, "links": links}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--out")
    a = ap.parse_args()
    g = build(a.repo)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(g), encoding="utf8")
    print(f"{len(g['nodes'])} nodes, {len(g['links'])} links")
