"""PreToolUse(Grep): send the first broad repo-wide search to ask.py; exact greps and repeats pass."""
import json, os, re, sys, tempfile
from common import find_up, is_big

root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# plain words or word|word: a concept search, not an exact one
BROAD = re.compile(r"^\(?[A-Za-z_][\w ]*(\|[A-Za-z_][\w ]*)*\)?$")


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
    # without a graphify graph ask.py indexes the repo itself, worth it only for big repos
    if not graph and not is_big(cwd):
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
    via = f' --graph "{graph}"' if graph else ""
    kw = ",".join(dict.fromkeys(w.lower() for w in re.split(r"[|() ]+", pat) if w))
    # the grep still runs: a deny costs a full turn when the agent repeats it anyway
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": f'Repo has a code index. For concept searches try: python "{root}/ask.py" "<task>"{via} '
                             f"--kw {kw},<more synonyms> (~200 tokens, files + lines). It finds the area, not every use."}}))


main()
