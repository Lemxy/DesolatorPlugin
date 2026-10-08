"""PreToolUse(Read): block whole reads of big files; a slice or a search is enough."""
import json, os, sys

MAX_BYTES = int(os.environ.get("DESOLATOR_READ_MAX", "40000"))
# images and pdfs are rendered, not tokenized as text
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ipynb"}


def main():
    try:
        h = json.load(sys.stdin)
        t = h["tool_input"]
        path = t["file_path"]
        size = os.path.getsize(path)
    except Exception:
        return
    if (size <= MAX_BYTES or t.get("offset") or t.get("limit") or os.path.splitext(path)[1].lower() in SKIP_EXT
            or os.environ.get("DESOLATOR_ALLOW_BIG_READ") == "1"):
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"{os.path.basename(path)} is {size // 1024} KB (~{size // 4} tokens) and stays in context "
                                    "for the rest of the session. Grep for the part you need (or ask.py), then Read with "
                                    "offset/limit around it."}}))


main()
