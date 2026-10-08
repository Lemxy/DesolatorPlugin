"""bench_ask.py: does ask.py find the right file? graphify graph vs built-in indexer vs no graph.
Usage: python bench_ask.py <repo> [--graph <repo>/graphify-out/graph.json] [--n 150] [--seed 1]
Questions are the first sentence of a docstring/JSDoc, the target is the file that holds it.
The target's own comment is removed from the content index so the text cannot be matched directly,
and the symbol's name words are removed from the question.
"""
import argparse, ast, json, os, pathlib, random, re, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ask as A
from indexer import SKIP_DIRS, build

JSD = re.compile(r"/\*\*((?:(?!\*/).)*?)\*/\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
                 r"(?:function\*?|class|interface|const|type|enum)\s+(\w+)", re.S)
JS_EXT = {".js", ".jsx", ".ts", ".tsx"}


def first_sentence(text):
    lines = [re.sub(r"^\s*\*+\s?", "", l).strip() for l in text.splitlines()]
    keep = []
    for l in lines:
        if l.startswith("@") or (not l and keep):
            break
        if l:
            keep.append(l)
    return re.split(r"(?<=[.!?])\s", " ".join(keep))[0].strip()


def comments(path):
    # (symbol, full comment text, first sentence)
    src = path.read_text(encoding="utf8", errors="ignore")
    out = []
    if path.suffix == ".py":
        try:
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            return out
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d = ast.get_docstring(n)
                if d:
                    out.append((n.name, d, first_sentence(d)))
    elif path.suffix in JS_EXT:
        for m in JSD.finditer(src):
            out.append((m.group(2), m.group(1), first_sentence(m.group(1))))
    return out


def is_test(rel):
    low = rel.lower()
    return any(x in low for x in ("test", "spec", "mock", "fixture", "__init__", "example"))


def make_questions(root, n, seed):
    pool = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for nm in names:
            p = pathlib.Path(d, nm)
            rel = p.relative_to(root).as_posix()
            if p.suffix not in JS_EXT | {".py"} or is_test(rel) or p.stat().st_size > A.MAX_BYTES:
                continue
            for sym, full, sent in comments(p):
                drop = {w for w in A.words(sym)}
                q = " ".join(w for w in re.split(r"\s+", sent) if not set(A.words(w)) & drop)
                if len([w for w in A.words(q) if w not in A.STOP]) >= 4 and not sym.startswith("_"):
                    pool.append((q, rel, full))
    random.Random(seed).shuffle(pool)
    # one question per file keeps big files from dominating
    seen, out = set(), []
    for q, rel, full in pool:
        if rel not in seen:
            seen.add(rel)
            out.append((q, rel, full))
        if len(out) == n:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--graph")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gw", type=float, default=A.GW)
    ap.add_argument("--out", help="write per-question results as json")
    a = ap.parse_args()
    A.GW = a.gw
    root = pathlib.Path(a.repo).resolve()
    gpath = a.graph or str(root / "graphify-out" / "graph.json")
    qs = make_questions(root, a.n, a.seed)

    systems = {"own graph": None, "no graph": "EMPTY"}
    graphify = os.path.isfile(gpath)
    if graphify:
        systems = {"graphify": gpath, **systems}
    else:
        print(f"(no graphify graph at {gpath}, skipping that system)")

    cache, build_s = {}, {}
    real_load = A.load

    def load(path, rt=None):
        if path not in cache:
            t = time.perf_counter()
            if path == "EMPTY":
                cache[path] = ({"nodes": [], "links": []}, defaultdict(int))
            else:
                g, deg = real_load(path, rt)
                if path:
                    # graphify docstring nodes carry the target's comment text
                    g["nodes"] = [n for n in g["nodes"] if " " not in n["label"]]
                cache[path] = (g, deg)
            build_s[path] = time.perf_counter() - t
        return cache[path]
    A.load = load
    A.build_cached = build  # time real indexing, not the cache

    tf = A.index(root)
    A._TF[root] = tf
    df = defaultdict(int)
    for c in tf.values():
        for w in c:
            df[w] += 1
    res = {(s, m): [] for s in systems for m in ("question", "keywords")}
    for q, rel, full in qs:
        gone = defaultdict(int)
        for w in A.words(full):
            gone[w] += 1
        saved = {w: tf[rel][w] for w in gone if w in tf[rel]}
        for w, c in gone.items():
            if w in tf[rel]:
                tf[rel][w] = max(0, tf[rel][w] - c)
        # stand-in for the agent: the 8 rarest question words that exist in the repo
        gone_df = {w for w in saved if tf[rel][w] == 0}
        cnt = {w: df[w] - (w in gone_df) for w in {w for w in A.words(q) if w not in A.STOP and w in df}}
        kw = sorted((w for w in cnt if cnt[w] > 0), key=lambda w: cnt[w])[:8]
        for s, gp in systems.items():
            for m in ("question", "keywords"):
                t = time.perf_counter()
                r = A.ask(q, gp, top=12, root=root, kw=kw if m == "keywords" else None)
                dt = time.perf_counter() - t
                files = [f for f, _ in r]
                res[(s, m)].append((files.index(rel) + 1 if rel in files else 0, len(A.fmt(r)) // 4, dt))
        for w, c in saved.items():
            tf[rel][w] = c

    n = len(qs)
    print(f"\n{root.name}: {n} questions, {len(tf)} indexed files\n")
    print(f"{'system':<20}{'R@1':>6}{'R@3':>6}{'R@8':>6}{'R@12':>6}{'MRR':>7}{'tok/ans':>9}{'rank ms':>9}{'build s':>9}{'cold CLI s':>12}")
    for (s, m), rows in res.items():
        rk = [r for r, _, _ in rows]
        at = lambda k: sum(1 for r in rk if 0 < r <= k) / n
        mrr = sum(1 / r for r in rk if r) / n
        gp = systems[s]
        cli = [sys.executable, os.path.join(HERE, "ask.py"), qs[0][0], "--root", str(root)]
        if gp is None:
            cli.append("--own")
        elif gp != "EMPTY":
            cli += ["--graph", gp]
        if gp == "EMPTY":
            cold = float("nan")
        else:
            t = time.perf_counter()
            subprocess.run(cli, capture_output=True)
            cold = time.perf_counter() - t
        print(f"{s + ' / ' + m:<20}{at(1):6.2f}{at(3):6.2f}{at(8):6.2f}{at(12):6.2f}{mrr:7.2f}"
              f"{sum(t for _, t, _ in rows) / n:9.0f}{sum(d for _, _, d in rows) / n * 1000:9.0f}{build_s[gp]:9.2f}{cold:12.2f}")
    if a.out:
        json.dump({"questions": [(q, rel) for q, rel, _ in qs], "ranks": {f"{s}/{m}": [r for r, _, _ in v] for (s, m), v in res.items()}},
                  open(a.out, "w", encoding="utf8"), ensure_ascii=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
