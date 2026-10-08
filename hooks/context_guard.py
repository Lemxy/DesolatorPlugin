"""UserPromptSubmit: warn the user when the session context is large, since every message re-reads it."""
import json, os, sys, tempfile

WARN_AT = int(os.environ.get("DESOLATOR_CTX_WARN", "150000"))
STEP = 50000
TAIL_BYTES = 4_000_000


def last_context(path):
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
        lines = f.read().decode("utf8", "ignore").splitlines()
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") != "assistant" or m.get("isSidechain"):
            continue
        u = (m.get("message") or {}).get("usage") or {}
        if u:
            return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return 0


def main():
    try:
        h = json.load(sys.stdin)
        ctx = last_context(h["transcript_path"])
    except Exception:
        return
    if ctx < WARN_AT:
        return
    # warn once per 50k step, not on every message
    mark = os.path.join(tempfile.gettempdir(), f"desolator-ctx-{h.get('session_id', 'x')}")
    step = ctx // STEP
    try:
        if int(open(mark).read()) >= step:
            return
    except (OSError, ValueError):
        pass
    open(mark, "w").write(str(step))
    print(json.dumps({"systemMessage": f"Desolator: context is {ctx // 1000}k tokens and every message re-reads it. "
                                       "Finished a task? Start a new session or /clear. Need history? /compact."}))


main()
