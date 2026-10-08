---
name: rules
description: Code rules that keep diffs small and code free of duplicates. Use before writing or reviewing a non-trivial change.
---
# Rules

1. **Comments:** why only, max 8 words, one per function. No docstrings, no history. Complex logic: up to 2 lines. Leave others' comments alone.
2. **Search first:** before writing a helper, hook, constant or markup, grep (or ask.py) by name and by meaning. Found one: reuse it. Close but not quite: extend it, do not add a second variant.
3. **Rule of three:** the same block (>3 lines) a second time: think. A third time: extract it and replace all copies in the same change.
4. **Write only what is unique:** token checks, busy/try/finally, error parsing, logging, clipboard, hidden process windows live in one place and are called in one line.
5. **One seam per cross-cutting concern:** auth, error logging, path normalization, process flags, HTTP call with error parsing. No seam yet: create it first.
6. **Data as tables:** repeated rows (settings, colors, prices, i18n pairs, class sets) go in an array or object and a loop. Values the server owns (prices, limits) are not copied to the client.
7. **Constants once:** numbers and strings used more than once get one named constant. One check, one implementation.
8. **No bloat:** no extra wrapper layers, no guards for cases that cannot happen (guard the boundaries: user input, server, file system), ignored errors in one line, no abstraction without two real callers.
9. **One job per file:** over ~400 lines usually means several jobs; split into sibling files.
10. **Before done:** Did I repeat a block I saw elsewhere? Is more than 3 lines of my function boilerplate? Did I add a second way to do something the project already does?
