"""stats.py: where did the tokens go? Reads Claude Code transcripts of this project.
Usage: python stats.py [--sessions 5] [--project <dir>] [--file <transcript.jsonl>]"""
import argparse, json, pathlib, re, sys
from collections import defaultdict


def project_dir(cwd):
    # Claude Code names the folder after the path, non-alnum -> '-'
    return pathlib.Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def size(c):
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(len(x.get("text", "")) if isinstance(x, dict) else len(str(x)) for x in c)
    return len(str(c))


def scan(path):
    seen, names = set(), {}
    s = dict(turns=0, inp=0, write=0, read=0, out=0, peak=0)
    tools = defaultdict(lambda: [0, 0])
    for line in open(path, encoding="utf8", errors="ignore"):
        try:
            m = json.loads(line)
        except ValueError:
            continue
        msg = m.get("message") or {}
        if m.get("type") == "assistant":
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    names[b["id"]] = b["name"]
            u, mid = msg.get("usage"), msg.get("id")
            # one message is streamed as several lines with the same usage
            if not u or mid in seen:
                continue
            seen.add(mid)
            s["turns"] += 1
            s["inp"] += u.get("input_tokens", 0)
            s["write"] += u.get("cache_creation_input_tokens", 0)
            s["read"] += u.get("cache_read_input_tokens", 0)
            s["out"] += u.get("output_tokens", 0)
            if not m.get("isSidechain"):
                s["peak"] = max(s["peak"], u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                + u.get("cache_read_input_tokens", 0))
        elif m.get("type") == "user" and isinstance(msg.get("content"), list):
            for b in msg["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    t = tools[names.get(b.get("tool_use_id"), "?")]
                    t[0] += 1
                    t[1] += size(b.get("content")) // 4
    return s, tools


def k(n):
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--sessions", type=int, default=5)
    a.add_argument("--project", default=None)
    a.add_argument("--file", default=None)
    o = a.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if o.file:
        files = [pathlib.Path(o.file)]
    else:
        d = project_dir(pathlib.Path(o.project or ".").resolve())
        files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:o.sessions]
        if not files:
            sys.exit(f"no transcripts in {d}")
    allt = defaultdict(lambda: [0, 0])
    print(f"{'session':10} {'turns':>5} {'peak ctx':>8} {'cache rd':>8} {'cache wr':>8} {'output':>7}")
    for f in files:
        s, tools = scan(f)
        print(f"{f.stem[:8]:10} {s['turns']:5} {k(s['peak']):>8} {k(s['read']):>8} {k(s['write']):>8} {k(s['out']):>7}")
        for n, (c, t) in tools.items():
            allt[n][0] += c
            allt[n][1] += t
    print("\ntool results that entered context (each is re-read on every later turn):")
    for n, (c, t) in sorted(allt.items(), key=lambda kv: -kv[1][1])[:10]:
        print(f"  {n:28} {c:4} calls  ~{k(t):>5} tokens  ~{k(t // max(c, 1)):>4}/call")


if __name__ == "__main__":
    main()
