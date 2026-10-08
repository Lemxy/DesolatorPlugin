"""PreToolUse(Write): block full rewrites of big existing files; Edit sends only the change."""
import json, os, sys

MAX_BYTES = int(os.environ.get("DESOLATOR_WRITE_MAX", "20000"))


def main():
    try:
        h = json.load(sys.stdin)
        path = h["tool_input"]["file_path"]
        size = os.path.getsize(path)
    except Exception:
        return
    if size <= MAX_BYTES or os.environ.get("DESOLATOR_ALLOW_BIG_WRITE") == "1":
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"{os.path.basename(path)} already exists and is {size // 1024} KB. Rewriting it costs "
                                    f"~{size // 4} output tokens. Use Edit for the changed parts instead."}}))


main()
