"""Summary table and bench/results.svg from e2e jsonl files.
Usage: python bench/make_chart.py bench/results/*.jsonl
The chart labels are rounded to the nearest 5%; exact values are printed in the table."""
import json, pathlib, sys

rows = [json.loads(l) for f in sys.argv[1:] for l in open(f, encoding="utf8")]
rows = [r for r in rows if not r.get("error")]
by = {a: [r for r in rows if r["arm"] == a] for a in ("base", "full")}
tot = lambda a, k: sum(r[k] for r in by[a])
PARAMS = [("Tokens, total (incl. cache reads)", "gross_tokens"), ("Fresh input tokens", "fresh_input"),
          ("Output tokens (replies)", "output_tokens"), ("Cost, USD", "cost"),
          ("Turns", "turns"), ("Wall time", "wall_s")]
exact, rnd = [], []
for label, k in PARAMS:
    saved = 100 * (1 - tot("full", k) / tot("base", k))
    exact.append((label, tot("base", k), tot("full", k), saved))
    rnd.append(5 * round(saved / 5))
n = len(by["base"])
ok = {a: sum(r["correct"] for r in by[a]) for a in by}
print(f"runs per arm: {n}; correct base {ok['base']}/{n}, full {ok['full']}/{len(by['full'])}")
print("| parameter | without plugin | with plugin | saved |\n|---|---|---|---|")
for (label, b, f, s), k in zip(exact, PARAMS):
    fmt = (lambda v: f"${v:.2f}") if k[1] == "cost" else (lambda v: f"{v:,.0f}")
    print(f"| {label} | {fmt(b)} | {fmt(f)} | {s:.0f}% |")

W, H, L, BAR = 760, 90 + 62 * len(PARAMS), 250, 440
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI,Helvetica,Arial,sans-serif">',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
       f'<text x="20" y="30" font-size="17" font-weight="600" fill="#1f2328">Desolator: end-to-end, same questions, same answers</text>',
       f'<text x="20" y="52" font-size="12" fill="#57606a">{n} runs per arm (8 tasks x 2 reps), Sonnet, {ok["full"]}/{len(by["full"])} correct with and {ok["base"]}/{n} without. Without plugin = 100%.</text>']
for i, ((label, b, f, s), r) in enumerate(zip(exact, rnd)):
    y = 80 + i * 62
    w_full = max(2, BAR * f / b)
    svg += [f'<text x="20" y="{y + 18}" font-size="13" fill="#1f2328">{label}</text>',
            f'<rect x="{L}" y="{y}" width="{BAR}" height="18" rx="3" fill="#d0d7de"/>',
            f'<text x="{L + BAR + 8}" y="{y + 14}" font-size="12" fill="#57606a">100%</text>',
            f'<rect x="{L}" y="{y + 24}" width="{w_full:.0f}" height="18" rx="3" fill="#1a7f37"/>',
            f'<text x="{L + w_full + 8:.0f}" y="{y + 38}" font-size="13" font-weight="600" fill="#1a7f37">-{r}%</text>']
svg.append("</svg>")
out = pathlib.Path(__file__).parent / "results.svg"
out.write_text("\n".join(svg), encoding="utf8")
print("wrote", out, "rounded:", dict(zip([p[1] for p in PARAMS], rnd)))
