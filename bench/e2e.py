"""End-to-end benchmark: `claude -p` on public repos, bare Claude Code vs this plugin + `slim.py code`.

    python bench/setup_e2e.py            # clone repos, prepare work/base and work/full
    python bench/e2e.py --reps 2         # 8 tasks x 2 arms x 2 reps = 32 runs (about 2.5M tokens)
    python bench/make_chart.py <jsonl>   # table + results.svg

Both arms run with --setting-sources so user-level plugins and settings do not leak in; they differ in
the plugin (--plugin-dir) and the slim deny rules in work/full/<repo>/.claude/settings.local.json.
The prompt asks nothing about brevity, so the plugin's own reply-style hint is what gets measured.
"""
import argparse, json, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path(__file__).resolve().parent / "work"

# (repo, question, strings the answer must ALL mention to count as correct)
TASKS = [
    ("django", "what happens when a POST with a wrong password hits the admin login view: which class validates the credentials (file), which function actually checks them, and where the user_login_failed signal is sent", ["forms.py", "authenticate", "user_login_failed"]),
    ("django", "how the migration autodetector decides between AddField and AlterField operations: which methods generate them", ["autodetector.py", "generate_added_fields", "generate_altered_fields"]),
    ("django", "how queryset.filter(a__b=1) across a relation is turned into joins: which file and which functions resolve the lookup path and set up the joins", ["query.py", "setup_joins", "names_to_path"]),
    ("django", "how the {% csrf_token %} template tag gets its token value: which node class implements the tag and which function produces the token", ["defaulttags.py", "CsrfTokenNode", "get_token"]),
    ("flask", "what happens from a WSGI call until the view return value becomes a Response: name the main methods in order", ["wsgi_app", "full_dispatch_request", "make_response"]),
    ("flask", "which method runs the before_request functions and how blueprint-level and app-level ones are ordered", ["preprocess_request"]),
    ("requests", "which functions rebuild the method and the auth header when following a redirect", ["rebuild_auth", "rebuild_method"]),
    ("requests", "how a connection adapter is chosen for a URL and where SSL certificates are verified", ["get_adapter", "cert_verify"]),
]
PROMPT = "In this repository, which file and function implement {q}? Explore the code as needed and do not edit anything."


def run(arm, repo, q, model):
    cmd = [shutil.which("claude"), "-p", PROMPT.format(q=q), "--model", model,
           "--setting-sources", "project,local" if arm == "full" else "project",
           "--output-format", "stream-json", "--verbose", "--max-turns", "25", "--max-budget-usd", "1.5",
           "--no-session-persistence", "--allowedTools", "Read", "Grep", "Glob", "Bash",
           "--disallowedTools", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]
    if arm == "full":
        cmd += ["--plugin-dir", str(ROOT)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=WORK / arm / repo, capture_output=True, text=True, encoding="utf8")
    wall = time.perf_counter() - t0
    res, tools = None, []
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            tools += [c["name"] for c in e["message"].get("content", []) if c.get("type") == "tool_use"]
        if e.get("type") == "result":
            res = e
    if res is None:
        return dict(arm=arm, repo=repo, q=q, error=(p.stdout or p.stderr)[-300:])
    u = res.get("usage", {})
    ans = res.get("result", "") or ""
    return dict(arm=arm, repo=repo, q=q, error=ans if res.get("is_error") else None, turns=res.get("num_turns"),
                cost=res.get("total_cost_usd"), output_tokens=u.get("output_tokens"),
                fresh_input=u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
                cache_read=u.get("cache_read_input_tokens", 0),
                gross_tokens=sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")),
                wall_s=round(wall, 1), answer=ans, tools=tools)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--reps", type=int, default=2)
    a.add_argument("--model", default="sonnet")
    a.add_argument("--out", default=str(pathlib.Path(__file__).parent / "results" / "run.jsonl"))
    o = a.parse_args()
    out = pathlib.Path(o.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for rep in range(o.reps):
        # alternate arm order so drift in load or cache state does not favour one arm
        arms = ("base", "full") if rep % 2 == 0 else ("full", "base")
        for repo, q, gt in TASKS:
            for arm in arms:
                r = run(arm, repo, q, o.model)
                r["gt"], r["rep"] = gt, rep
                r["correct"] = bool(r.get("answer")) and all(g in r["answer"] for g in gt)
                with open(out, "a", encoding="utf8") as f:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print(rep, arm, repo, "ERR " + r["error"][:80] if r.get("error") else
                      f"turns={r['turns']} gross={r['gross_tokens']} cost=${r['cost']:.3f} correct={r['correct']}", flush=True)
                if r.get("error"):
                    sys.exit("stopping: " + r["error"][:200])


if __name__ == "__main__":
    main()
