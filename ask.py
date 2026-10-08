"""ask.py: natural-language question -> compact file/symbol list from a graphify graph.json.
Usage: python ask.py "how does login work" [--graph graphify-out/graph.json] [--top 8]
"""
import json, math, os, re, sys, argparse, pathlib
from collections import defaultdict

STOP = set("a an the is are was were do does did how what where which who why when to of in on for and or "
           "with from by it its this that work works use used using get gets make makes handle handles "
           "happen happens code file files function functions".split())
# generic synonyms; a repo adds its own in <repo>/synonyms.json {"word": ["syn", ...]}
SYN = {
    "login": ["auth", "signin", "session", "token", "password"],
    "auth": ["login", "session", "token"],
    "payment": ["pay", "checkout", "payout"],
    "pay": ["payment", "payout"],
    "update": ["updater", "upgrade"],
    "mail": ["email", "smtp"],
    "email": ["mail", "verify"],
    "limit": ["limiter", "throttle"],
    "download": ["fetch", "updater"],
}
SKIP_DIRS = {".git", "node_modules", "graphify-out", "dist", "build", "target", "venv", ".venv", "__pycache__", ".next"}
TEXT_EXT = {".js", ".jsx", ".ts", ".tsx", ".rs", ".md", ".py", ".go", ".java", ".kt", ".cs", ".rb", ".php", ".vue", ".svelte", ".c", ".cpp", ".h", ".swift"}
MAX_BYTES = 500_000


CYR = re.compile("[а-яё]")


SPLIT = r"[^A-Za-z0-9А-Яа-яЁё]+"


def words(s):
    # keep perMachine whole too, so "permachine" matches
    whole = [w for w in re.split(SPLIT, s) if w and w.lower() != w and not w.isupper()]
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [w for w in re.split(SPLIT, s.lower()) if w] + [w.lower() for w in whole]


def stem(w):
    # russian endings vary: обновление/обновления
    return w[:max(4, len(w) - 2)] if CYR.search(w) else w


def match(t, w):
    t, w = stem(t), stem(w)
    return len(min(t, w, key=len)) >= 4 and (w.startswith(t) or t.startswith(w))


def load(path):
    p = pathlib.Path(path)
    if not p.is_file():
        sys.exit(f"graph not found: {path}. Run `graphify update <repo>` once.")
    g = json.load(open(p, encoding="utf8"))
    deg = defaultdict(int)
    for e in g["links"]:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    return g, deg


def user_syn(root):
    f = pathlib.Path(root, "synonyms.json")
    return json.loads(f.read_text(encoding="utf8")) if f.is_file() else {}


def terms(q, extra=None):
    syn = {**SYN, **(extra or {})}
    base = [w for w in words(q) if w not in STOP]
    out = {w: 1.0 for w in base}
    for w in base:
        for k, syns in syn.items():
            if match(k, w):
                for s in syns:
                    out.setdefault(s, 0.6)
    return out


def noise(n, d):
    lab = n["label"]
    # constants, externals and hubs like t() carry no signal
    return not n.get("source_file") or lab.isupper() or d > 60


_TF = {}


def index(root):
    tf = {}
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in names:
            p = pathlib.Path(d, n)
            if p.suffix in TEXT_EXT and p.stat().st_size <= MAX_BYTES:
                c = defaultdict(int)
                for w in words(p.read_text(encoding="utf8", errors="ignore")):
                    c[w] += 1
                tf[p.relative_to(root).as_posix()] = c
    return tf


def content_score(T, root):
    # TF-IDF of query terms over file text; rare words weigh more
    if root not in _TF:
        _TF[root] = index(root)
    tf = _TF[root]
    vocab = {w for c in tf.values() for w in c}
    out = {}
    for t, wt in T.items():
        ws = [w for w in vocab if match(t, w)]
        hit = {f: sum(c.get(w, 0) for w in ws) for f, c in tf.items()}
        hit = {f: n for f, n in hit.items() if n}
        if not hit:
            continue
        idf = math.log(len(tf) / len(hit))
        for f, n in hit.items():
            out[f] = out.get(f, 0) + wt * idf * min(math.log1p(n), 2)
    return out


def find_root(gpath):
    # wrong root silently disables content scoring
    d = pathlib.Path(gpath).resolve().parent
    if d.name == "graphify-out":
        return d.parent
    for up in [d, *d.parents]:
        if (up / ".git").exists():
            return up
    return d.parent


def find_graph(start="."):
    d = pathlib.Path(start).resolve()
    for up in [d, *d.parents]:
        if (up / "graphify-out" / "graph.json").is_file():
            return str(up / "graphify-out" / "graph.json")
    return "graphify-out/graph.json"


def ask(q, gpath, top=12, kw=None, content=True, neighbors=True, slots=0, scored=False, root=None):
    g, deg = load(gpath)
    # kw: keywords already chosen by the calling agent, skips guessing
    root = pathlib.Path(root).resolve() if root else find_root(gpath)
    T = {w.lower(): 1.0 for w in kw} if kw else terms(q, user_syn(root))
    nodes = {n["id"]: n for n in g["nodes"]}
    score = {}
    for i, n in nodes.items():
        if noise(n, deg[i]):
            continue
        lw, pw = words(n["label"]), words(n["source_file"])
        s = 0.0
        for t, wt in T.items():
            if any(match(t, w) for w in lw):
                s += 3 * wt
            elif any(match(t, w) for w in pw):
                s += 1 * wt
        if s:
            score[i] = s / (1 + 0.1 * math.log1p(deg[i]))
    seeds = sorted(score, key=score.get, reverse=True)[:top * 2]
    nbr = defaultdict(list)
    for e in g["links"]:
        if e["relation"] == "calls":
            nbr[e["source"]].append(e["target"])
            nbr[e["target"]].append(e["source"])
    files = defaultdict(lambda: [0.0, {}])
    for i in seeds:
        for j, bonus in [(i, 1.0)] + [(k, 0.3) for k in nbr[i][:3] if k in nodes and not noise(nodes[k], deg[k])]:
            n = nodes[j]
            f = files[n["source_file"]]
            f[0] += score.get(j, 0.5) * bonus
            f[1][n["label"]] = n.get("source_location", "")
    named = {}
    for f in {n["source_file"] for n in nodes.values() if n.get("source_file")}:
        base = words(f.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        # file name match is the strongest signal
        b = sum(4 * wt for t, wt in T.items() if any(match(t, w) for w in base))
        if b:
            files[f][0] += b
            named[f] = b
    if content:
        for f, c in content_score(T, root).items():
            files[f][0] += c
    if neighbors:
        # files linked by import/call to the top 3 are probably same topic
        fnbr = defaultdict(set)
        for e in g["links"]:
            a, b = nodes.get(e["source"]), nodes.get(e["target"])
            if a and b and a.get("source_file") and b.get("source_file") and a["source_file"] != b["source_file"]:
                fnbr[a["source_file"]].add(b["source_file"])
                fnbr[b["source_file"]].add(a["source_file"])
        lead = sorted(files.items(), key=lambda kv: kv[1][0], reverse=True)[:3]
        for f, v in lead:
            for nb in sorted(fnbr[f])[:6]:
                files[nb][0] += 0.25 * v[0]
    ranked = sorted(files.items(), key=lambda kv: kv[1][0], reverse=True)
    out = ranked[:top]
    # guarantee slots for best file-name matches
    keep = sorted(named, key=lambda f: (named[f], files[f][0]), reverse=True)[:slots]
    for f in keep:
        if f not in {r[0] for r in out}:
            for idx in range(len(out) - 1, -1, -1):
                if out[idx][0] not in keep:
                    out[idx] = (f, files[f])
                    break
    if scored:
        return [(f, list(v[1].items())[:4], v[0]) for f, v in out]
    return [(f, list(v[1].items())[:4]) for f, v in out]


CHUNK = 1500


def chunks(lines):
    # long sections split at bullets so answers stay small
    out, cur = [], []
    for line in lines:
        if cur and (line.startswith("- ") or not line.strip()) and len("\n".join(cur).encode()) > CHUNK:
            out.append(cur)
            cur = []
        cur.append(line)
    return out + [cur]


def sections(root):
    out = []
    for p in sorted(pathlib.Path(root).rglob("*.md")):
        title, head, buf = p.stem, p.stem, []
        for line in p.read_text(encoding="utf8", errors="ignore").splitlines() + ["# "]:
            if line.startswith("#"):
                for part in chunks(buf):
                    if "".join(part).strip():
                        out.append((p.relative_to(root).as_posix(), head, "\n".join(part).strip()))
                sub = line.lstrip("#").strip()
                if line.startswith("# "):
                    title, head = sub, sub
                else:
                    # card title gives subsections their topic
                    head = f"{title} / {sub}"
                buf = []
            else:
                buf.append(line)
    return out


def ask_map(q, root, kw=None, budget=800):
    # docs: return the matching sections themselves, not file names
    T = {w.lower(): 1.0 for w in kw} if kw else terms(q)
    secs = sections(root)
    toks = [(words(t), words(h), words(f)) for f, h, t in secs]
    score = [0.0] * len(secs)
    for t, wt in T.items():
        hit = [sum(match(t, w) for w in body) for body, _, _ in toks]
        n = sum(1 for x in hit if x)
        if not n:
            continue
        idf = math.log(1 + len(secs) / n)
        for i, (body, head, fname) in enumerate(toks):
            s = min(math.log1p(hit[i]), 2) + 3 * any(match(t, w) for w in head) + 2 * any(match(t, w) for w in fname)
            score[i] += wt * idf * s
    out, used, best = [], 0, max(score, default=0)
    for i in sorted(range(len(secs)), key=lambda i: -score[i]):
        f, h, t = secs[i]
        cost = len(t.encode()) // 3
        # weak matches add tokens, not answers
        if score[i] < 0.35 * best or best <= 0 or (out and used + cost > budget):
            continue
        out.append(f"### {f} # {h}\n{t}")
        used += cost
    return "\n\n".join(out) or "no matching section"


def fmt(res):
    return "\n".join(f + (": " + ", ".join(f"{l}@{loc}" for l, loc in syms) if syms else "") for f, syms in res)


if __name__ == "__main__":
    # Windows consoles default to cp1251 and garble paths
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("q")
    p.add_argument("--graph", default=None, help="default: nearest graphify-out/graph.json up from cwd")
    p.add_argument("--root", default=None, help="repo root for content search; default from graph path")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--kw", help="comma-separated keywords chosen by the agent")
    p.add_argument("--map", nargs="?", const="ProjectMap", help="search markdown docs in this folder instead of code")
    p.add_argument("--budget", type=int, default=800, help="max tokens of doc text for --map")
    a = p.parse_args()
    kw = a.kw.split(",") if a.kw else None
    print(ask_map(a.q, a.map, kw, a.budget) if a.map else fmt(ask(a.q, a.graph or find_graph(), a.top, kw, root=a.root)))
