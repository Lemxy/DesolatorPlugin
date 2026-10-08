"""slim.py: hide tools a coding session does not need, so every turn re-reads less context.
Usage: python slim.py [code|core] [--scan] [--user] [--also A,B] [--dry-run] | python slim.py --undo [--user]
Default writes <cwd>/.claude/settings.local.json (this project only)."""
import argparse, json, pathlib, subprocess, sys

# tool schemas re-sent on every turn; WebSearch/WebFetch stay on purpose
CODE = ["Artifact", "ArtifactComments", "ArtifactData", "CronCreate", "CronDelete", "CronList", "DesignSync",
        "EnterWorktree", "ExitWorktree", "ListAgents", "Monitor", "NotebookEdit", "PowerShell", "PushNotification",
        "RemoteTrigger", "ReportFindings", "ScheduleWakeup", "SendMessage", "mcp__claude_ai_Claude_Docs"]
CORE = CODE + ["Agent", "Task", "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "TaskStop", "TodoWrite", "ToolSearch"]
PROFILES = {"code": CODE, "core": CORE}


KEEP = {"Bash", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "Task", "Skill", "TodoWrite", "ToolSearch",
        "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "TaskStop", "WebSearch", "WebFetch"}


def scan():
    # one tiny Haiku call reports the real tool list of this setup
    r = subprocess.run("claude -p --model haiku --output-format stream-json --verbose --no-session-persistence",
                       input="Reply OK", capture_output=True, text=True, encoding="utf8", shell=True)
    for line in r.stdout.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("subtype") == "init":
            names = {t if not t.startswith("mcp__") else "mcp__" + t.split("__")[1] for t in m.get("tools", [])}
            return sorted(n for n in names if n not in KEEP)
    sys.exit("scan failed: " + r.stderr[-300:])


def target(user):
    base = pathlib.Path.home() if user else pathlib.Path.cwd()
    return base / ".claude" / ("settings.json" if user else "settings.local.json")


def read(p):
    return json.loads(p.read_text(encoding="utf8")) if p.is_file() else {}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("profile", nargs="?", default="code", choices=PROFILES)
    a.add_argument("--user", action="store_true", help="all projects (~/.claude/settings.json)")
    a.add_argument("--also", default="", help="extra tool or mcp__server names, comma-separated")
    a.add_argument("--undo", action="store_true")
    a.add_argument("--scan", action="store_true", help="find hideable tools and MCP servers of this setup")
    a.add_argument("--dry-run", action="store_true")
    o = a.parse_args()
    p = target(o.user)
    # remember what we added so undo never drops user rules
    mark = p.with_name("desolator-slim.json")
    s = read(p)
    deny = s.setdefault("permissions", {}).setdefault("deny", [])
    if o.undo:
        ours = set(read(mark).get("added", []))
        s["permissions"]["deny"] = [d for d in deny if d not in ours]
        if not o.dry_run:
            p.write_text(json.dumps(s, indent=2), encoding="utf8")
            mark.unlink(missing_ok=True)
        print(f"removed {len(ours)} rules from {p}")
        return
    want = PROFILES[o.profile] + [x for x in o.also.split(",") if x] + (scan() if o.scan else [])
    want = list(dict.fromkeys(want))
    added = [t for t in want if t not in deny]
    print(f"{p}: +{len(added)} deny rules ({o.profile}). WebSearch/WebFetch stay on. Takes effect in new sessions.")
    if o.dry_run:
        print(", ".join(added))
        return
    deny.extend(added)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=2), encoding="utf8")
    prev = read(mark).get("added", [])
    mark.write_text(json.dumps({"added": sorted(set(prev + added))}), encoding="utf8")


if __name__ == "__main__":
    sys.exit(main())
