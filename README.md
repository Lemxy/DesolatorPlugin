# Desolator

Token and cost saver for Claude Code. Every turn re-reads the whole context, so the plugin cuts what enters it: unused tool schemas, whole-file reads, long logs, broad searches.

## Install
```
claude plugin marketplace add Lemxy/DesolatorPlugin
claude plugin install desolator@desolator
```
Local checkout: `claude --plugin-dir <path>`. Requires Python on PATH (`python`).
Full guide (setup per project, settings, update, removal): [INSTALL.md](INSTALL.md).

## Parts

### Hooks (on by default)
- `context_guard.py` (UserPromptSubmit): warns once per 50k step when the session context passes 150k (`DESOLATOR_CTX_WARN`). Long sessions are most of real token use.
- `write_guard.py` (PreToolUse Write): blocks full rewrites of existing files over 20 KB (`DESOLATOR_WRITE_MAX`, bypass `DESOLATOR_ALLOW_BIG_WRITE=1`). Edit sends only the change.
- `read_guard.py` (PreToolUse Read): blocks whole reads of files over 40 KB (`DESOLATOR_READ_MAX`, bypass `DESOLATOR_ALLOW_BIG_READ=1`). Grep, then Read with offset/limit.
- `grep_route.py` (PreToolUse Grep): with a code graph, the first broad repo-wide Grep (`word` or `a|b`) is sent to ask.py. Regex, file/glob/type-scoped greps and repeats pass, so exhaustive searches still work. Off: `DESOLATOR_GREP_ROUTE=0`.
- `bash_trim.py` (PreToolUse Bash): build/test/install output over 120 lines -> first 40 + last 80 lines, full log in a temp file, exit code kept. Only in bypassPermissions mode or with `DESOLATOR_BASH_TRIM=1`: the wrapper breaks allowlist matching, so normal modes would prompt. Piped, chained or background commands pass.
- `route_context.py` (SessionStart): one-line hints only when they apply (code graph, `ProjectMap/`, big repo without index, markdown over 20 KB). Projects without these pay nothing.

### Tools
- `slim.py` / `/desolator:slim`: hides tools a coding session does not need (Artifact, Cron, Worktree, ...) via `permissions.deny`. WebSearch/WebFetch stay. `python slim.py` (this project), `--user` (all projects), `core` (also hides Agent/Task/TodoWrite), `--scan` (asks Haiku once for the real tool list, hides extra tools and MCP servers), `--undo`, `--dry-run`.
- `ask.py`: natural-language code search over a graphify graph. `uv tool install graphifyy`, then `graphify update <repo>` once. The agent supplies keywords (`--kw`); that is what makes recall work. Optional `<repo>/synonyms.json` (`{"word": ["syn"]}`).
- `mapsplit.py` + `ask.py --map`: split a big markdown map into cards (`ProjectMap/` + `INDEX.md`), then fetch only matching sections.
- `stats.py`: where the tokens went in the last sessions of a project (peak context, cache reads/writes, output, tool results by size).

### Skills and agents
- `skills/route`: find code with ask.py, delegate bulk mechanical edits to `scout`.
- `skills/rules`: code rules (comments why-only, max 8 words; no duplicates; rule of three).
- `agents/scout.md` (Haiku): bulk mechanical edits and log summaries, never logic.

## Measured
On a private Tauri + Node monorepo (~600 source files), Sonnet:
- slim, read-only question, same correct answer: 169k -> 82k raw tokens (-52%), cache-weighted -29%. Base context per turn 33.9k -> 15.1k.
- ask + agent keywords: recall 0.78-0.82 on 60 blind questions, ~200 tokens per answer. Without graphify edges (declarations only): 0.72.
- ask vs reading the relevant files: ~420 vs ~18.6k tokens for 3 questions. The answer is pointers, so a few slices still get read.
- `ask.py --map` on a 60 KB project map: fact found 7/8, ~820 tokens per answer vs ~10-20k for the whole file.
- Doc style, one section, real tokenizer: prose RU 794, terse RU 397, terse EN 368 tokens. Terseness saves ~50%, language ~7%.
- Reasoning language (EN vs RU), 10 runs: no stable cost difference; tool calls dominate output.
- Sonnet with ask: 3-9% fewer tokens on 12 of 12 easy bugs.

Numbers are per mechanism; an end-to-end benchmark is not done yet.
