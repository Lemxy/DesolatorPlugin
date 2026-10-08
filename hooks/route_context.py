import json, os, sys
from common import find_up, is_big

BIG_MD = 20000
root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def project_dir():
    try:
        return json.load(sys.stdin).get("cwd") or os.getcwd()
    except Exception:
        return os.getcwd()


def big_md(d):
    try:
        for f in os.listdir(d):
            q = os.path.join(d, f)
            if f.lower().endswith(".md") and os.path.isfile(q) and os.path.getsize(q) > BIG_MD:
                return q
    except OSError:
        pass
    return None


d = project_dir()
graph = find_up(d, os.path.join("graphify-out", "graph.json"))
docs = find_up(d, "ProjectMap")
if docs:
    sys.stdout.write(f'Project docs: do not read whole maps. python "{root}/ask.py" "<task>" --map "{docs}" --kw k1,k2,... returns only matching sections. '
                     "Docs you write or edit there: short bullets, paths and names, no prose, one card per area.\n")
big = None if docs else big_md(d)
if big:
    sys.stdout.write(f'{os.path.basename(big)} is over 20 KB: do not read it whole. Split once: python "{root}/mapsplit.py" "{big}" --out ProjectMap, then use ask.py --map. New docs: English, terse bullets. Comments stay why-only, max 8 words.\n')
if graph:
    sys.stdout.write(f'To find code: python "{root}/ask.py" "<task>" --graph "{graph}" --kw k1,k2,... (8-12 identifier keywords). Delegation: skill desolator:route. Comments: why only, max 8 words.\n')
elif is_big(d):
    # ask.py indexes the repo itself when there is no graphify graph
    sys.stdout.write(f'To find code: python "{root}/ask.py" "<task>" --kw k1,k2,... (8-12 identifier keywords). Delegation: skill desolator:route. Comments: why only, max 8 words.\n')
