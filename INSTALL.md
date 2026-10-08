# Install guide

## 1. Requirements
- Claude Code (CLI, desktop app or IDE extension).
- Python 3 on PATH as `python`. Check: `python --version`. On Windows, if only `py` works, install Python from python.org with "Add to PATH" checked.
- Code search (`ask.py`) needs nothing else: it indexes the repo itself. graphify is optional (`uv tool install graphifyy`, then `graphify update .`); `ask.py` uses its graph when it exists.

## 2. Install the plugin
From a terminal:
```
claude plugin marketplace add Lemxy/DesolatorPlugin
claude plugin install desolator@desolator
```
Or inside a Claude Code session:
```
/plugin marketplace add Lemxy/DesolatorPlugin
/plugin install desolator@desolator
```
Default scope is `user` (all projects). One project only: add `--scope project` to the install command.

Hooks load at session start: open a **new session** after installing.

## 3. Check it works
```
claude plugin list
```
`desolator@desolator` should show `Status: enabled`. In a session, `/desolator:slim --dry-run` lists the tools it would hide.

## 4. Per-project setup (once)
| Step | Command | Gives |
|---|---|---|
| Hide unused tools | `/desolator:slim` (or `--user` for all projects) | smaller context every turn |
| Code index (optional) | `graphify update .` in the repo root | Grep routing; `ask.py` works without it |
| Big markdown map | `python <plugin>/mapsplit.py PROJECT_MAP.md --out ProjectMap` | doc sections on demand |
| See where tokens go | `python <plugin>/stats.py --sessions 5` | per-session breakdown |

If you use graphify, re-run `graphify update .` after big code changes; a graphify graph does not refresh itself. The built-in index does.

`<plugin>` is the install folder, e.g. `~/.claude/plugins/cache/desolator/desolator/<version>`.

## 5. Settings
Set in your shell or in `settings.json` under `"env"`.

| Variable | Default | Effect |
|---|---|---|
| `DESOLATOR_CTX_WARN` | `150000` | context size that triggers the warning |
| `DESOLATOR_WRITE_MAX` | `20000` | bytes; bigger existing files cannot be rewritten whole |
| `DESOLATOR_ALLOW_BIG_WRITE` | unset | `1` disables the write guard |
| `DESOLATOR_READ_MAX` | `40000` | bytes; bigger files need offset/limit |
| `DESOLATOR_ALLOW_BIG_READ` | unset | `1` disables the read guard |
| `DESOLATOR_GREP_ROUTE` | on | `0` disables Grep -> ask.py routing |
| `DESOLATOR_BASH_TRIM` | bypass mode only | `1` always on, `0` off |

## 6. Update
```
claude plugin marketplace update desolator
claude plugin update desolator@desolator
```

## 7. Remove
```
/desolator:slim --undo
claude plugin uninstall desolator@desolator
claude plugin marketplace remove desolator
```
Run `slim --undo` first: deny rules live in your settings, not in the plugin.

## Troubleshooting
- **Hooks do nothing:** start a new session; check `python --version` works in the same shell.
- **`ask.py` finds nothing or the wrong area:** run it from inside the repo (or pass `--root`), and rerun once with different keywords.
- **A tool is missing after slim:** `/desolator:slim --undo`, or remove that entry from `permissions.deny`.
- **Grep was refused once:** intended. Repeat the same Grep and it runs.
