"""Shared by route_context.py and grep_route.py."""
import os

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt", ".cs", ".rb", ".php", ".vue", ".svelte", ".c", ".cpp", ".h", ".swift"}
SKIP = {".git", "node_modules", "graphify-out", "dist", "build", "target", "venv", ".venv", "__pycache__"}
BIG_REPO = 30


def find_up(d, rel):
    while True:
        p = os.path.join(d, rel)
        if os.path.exists(p):
            return p
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def is_big(d):
    n = 0
    for _, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP]
        n += sum(os.path.splitext(f)[1] in CODE_EXT for f in names)
        if n > BIG_REPO:
            return True
    return False
