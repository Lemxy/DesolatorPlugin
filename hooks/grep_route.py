"""PreToolUse(Grep): send the first broad repo-wide search to ask.py; exact greps and repeats pass."""
import json, os, re, sys, tempfile

root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# plain words or word|word: a concept search, not an exact one
BROAD = re.compile(r"^\(?[A-Za-z_][\w ]*(\|[A-Za-z_][\w ]*)*\)?$")


def find_up(d, rel):
    while True:
        p = os.path.join(d, rel)
        if os.path.exists(p):
            return p
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def main():
    if os.environ.get("DESOLATOR_GREP_ROUTE") == "0":
        return
    try:
        h = json.load(sys.stdin)
        t = h["tool_input"]
        pat = t["pattern"]
        cwd = h.get("cwd") or os.getcwd()
    except Exception:
        return
    path = t.get("path") or cwd
    # a single file or a narrow glob is already targeted
    if os.path.isfile(path) or t.get("glob") or t.get("type") or not BROAD.match(pat):
        return
    graph = find_up(cwd, os.path.join("graphify-out", "graph.json"))
    if not graph:
        return
    mark = os.path.join(tempfile.gettempdir(), f"desolator-grep-{h.get('session_id', 'x')}")
    try:
        seen = set(open(mark, encoding="utf8").read().splitlines())
    except OSError:
        seen = set()
    key = f"{path}\t{pat}"
    # nudge once per pattern so grep is never truly blocked
    if key in seen:
        return
    with open(mark, "a", encoding="utf8") as f:
        f.write(key + "\n")
    kw = ",".join(dict.fromkeys(w.lower() for w in re.split(r"[|() ]+", pat) if w))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f'Repo has a code index. Try first: python "{root}/ask.py" "<task>" --graph "{graph}" '
                                    f"--kw {kw},<more synonyms> (~200 tokens, files + lines). It finds the area, not every "
                                    "use: for renames or all usages, repeat the same grep and it will run."}}))


main()
