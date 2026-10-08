"""PreToolUse(Bash): long build/test output -> head + tail in context, full log on disk, exit code kept."""
import json, os, re, sys

HEAD, TAIL = 40, 80
# build/test/install tools whose logs run to thousands of lines
NOISY = re.compile(r"^\s*(?:[\w./-]*/)?(?:npm|pnpm|yarn|npx|bun|cargo|pytest|python -m pytest|go (?:test|build)|make|"
                   r"gradle|gradlew|mvn|tsc|eslint|jest|vitest|dotnet (?:build|test)|pip install|uv pip install)\b")


def main():
    try:
        h = json.load(sys.stdin)
        t = h["tool_input"]
        cmd = t["command"]
    except Exception:
        return
    # the wrapper defeats allowlist matching, so prompts appear in normal modes
    on = os.environ.get("DESOLATOR_BASH_TRIM")
    if on == "0" or (on != "1" and h.get("permission_mode") != "bypassPermissions"):
        return
    # already shaped by the agent, chained, or backgrounded: leave alone
    if t.get("run_in_background") or not NOISY.match(cmd) or re.search(r"[|><;&`]|\$\(", cmd):
        return
    n = HEAD + TAIL
    wrapped = (f'_l=$(mktemp); ( {cmd} ) >"$_l" 2>&1; _s=$?; _n=$(wc -l <"$_l"); '
               f'if [ "$_n" -gt {n} ]; then head -n {HEAD} "$_l"; '
               f'echo "... [$((_n-{n})) lines cut by desolator; full log: $_l]"; tail -n {TAIL} "$_l"; '
               f'else cat "$_l"; fi; exit $_s')
    # no permissionDecision: normal permission rules still apply
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {**t, "command": wrapped}}}))


main()
