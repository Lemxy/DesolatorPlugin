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
- `grep_route.py` (PreToolUse Grep): in a repo with a graphify graph or over 30 code files, the first broad repo-wide Grep (`word` or `a|b`) is sent to ask.py. Regex, file/glob/type-scoped greps and repeats pass, so exhaustive searches still work. Off: `DESOLATOR_GREP_ROUTE=0`.
- `bash_trim.py` (PreToolUse Bash): build/test/install output over 120 lines -> first 40 + last 80 lines, full log in a temp file, exit code kept. Only in bypassPermissions mode or with `DESOLATOR_BASH_TRIM=1`: the wrapper breaks allowlist matching, so normal modes would prompt. Piped, chained or background commands pass.
- `route_context.py` (SessionStart): one-line hints only when they apply (code graph, `ProjectMap/`, big repo (ask.py indexes it itself), markdown over 20 KB). Projects without these pay nothing.

### Tools
- `slim.py` / `/desolator:slim`: hides tools a coding session does not need (Artifact, Cron, Worktree, ...) via `permissions.deny`. WebSearch/WebFetch stay. `python slim.py` (this project), `--user` (all projects), `core` (also hides Agent/Task/TodoWrite), `--scan` (asks Haiku once for the real tool list, hides extra tools and MCP servers), `--undo`, `--dry-run`.
- `ask.py`: natural-language code search. No dependencies: `indexer.py` builds the symbol/call graph itself (Python via `ast`, JS/TS/Rust/Go/Java/C#/Ruby/PHP/Kotlin/Swift/C by regex), cached in the temp dir and refreshed when a file changes. A graphify `graphify-out/graph.json` is used if present (`--own` ignores it). The agent supplies keywords (`--kw`); that is what makes recall work. Optional `<repo>/synonyms.json` (`{"word": ["syn"]}`).
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
- `bench_ask.py` (reproducible, public code): question = first sentence of a docstring/JSDoc, target = its file; the target's own comment is removed from the text index and the symbol name from the question. Recall@12 / MRR, ask top 12, rarest-question-words as keywords:

  | corpus (questions) | graphify | built-in index | text only |
  |---|---|---|---|
  | Python stdlib, 555 files (150) | 0.76 / 0.41 | 0.70 / 0.40 | 0.76 / 0.42 |
  | pdf-lib TS source, 139 files (40) | 0.53 / 0.21 | 0.60 / 0.27 | 0.55 / 0.24 |
  | universal-modder Python, 154 files (9) | 0.89 / 0.57 | 0.89 / 0.53 | 0.89 / 0.57 |

  The built-in index matches graphify within noise (+-0.06) with no install. On this question type the graph adds nothing over the text index; its value is the `symbol@line` pointers. Cost per answer: ~105 tokens (built-in) vs ~54 (graphify). Latency: built-in index 0.1-3 s once (cached after), graphify graph load 0.15 s. Questions here are synthetic; the 60 human questions above are the closer proxy.
- ask vs reading the relevant files: ~420 vs ~18.6k tokens for 3 questions. The answer is pointers, so a few slices still get read.
- `ask.py --map` on a 60 KB project map: fact found 7/8, ~820 tokens per answer vs ~10-20k for the whole file.
- Doc style, one section, real tokenizer: prose RU 794, terse RU 397, terse EN 368 tokens. Terseness saves ~50%, language ~7%.
- Reasoning language (EN vs RU), 10 runs: no stable cost difference; tool calls dominate output.
- Sonnet with ask: 3-9% fewer tokens on 12 of 12 easy bugs.

Numbers are per mechanism; an end-to-end benchmark is not done yet.
