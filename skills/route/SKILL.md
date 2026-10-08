---
name: route
description: Find code with ask.py and delegate bulk mechanical edits to scout (Haiku) in repos with a code index.
---
# Route

## 1. Find code with `ask` (a script, no subagent)
Pick 8-12 lowercase identifier-style keywords from the task, with synonyms and the technical concept behind everyday wording (words that would appear in function, class or file names). Then:

```
python "${CLAUDE_PLUGIN_ROOT}/ask.py" "<task in one line>" --graph <repo>/graphify-out/graph.json --kw k1,k2,k3
```

- No graph yet: run `graphify update <repo>` once (parses code locally, no LLM), then ask.
- Read only the returned files and the lines around the listed symbols.
- Result misses the obvious area: rerun once with different keywords. Do not rerun more than twice.
- Default top is 12 files. For repos under ~30 modules add `--top 6`.

## 2. Who does what
| Work | Who |
|---|---|
| Normal implementation, bug fix, tests | the main session |
| Mechanical edit across many files, verifiable by grep or tests: rename, move, imports, format; log or test-output summary | `scout` (Haiku) |

## 3. Rules that keep it cheap
- A subagent costs about 55k tokens of fixed overhead. Do not spawn one for work under ~10 tool calls.
- Give a subagent a brief, never the conversation: `goal | files | acceptance command`.
- Haiku never decides behavior. If it answers NEEDS_JUDGEMENT, take the task back.
- Run the acceptance command yourself after any delegated edit.
