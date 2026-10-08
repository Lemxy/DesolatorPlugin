"""mapsplit.py: split one big markdown map into small cards (one per ## section) plus INDEX.md.
Usage: python mapsplit.py PROJECT_MAP.md [--out ProjectMap]. The source file is left untouched."""
import argparse, pathlib, re


TR = dict(zip("абвгдеёзийклмнопрстуфхцыэ", "abvgdeeziiklmnoprstufhcye"))
TR.update({"ж": "zh", "ч": "ch", "ш": "sh", "щ": "sch", "ю": "yu", "я": "ya", "ъ": "", "ь": ""})


def slug(h, n):
    h = "".join(TR.get(c, c) for c in h.lower())
    s = re.sub(r"[^a-z0-9]+", "-", h).strip("-")[:40]
    return f"{n:02d}-{s or 'section'}.md"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("src")
    a.add_argument("--out", default="ProjectMap")
    o = a.parse_args()
    out = pathlib.Path(o.out)
    out.mkdir(parents=True, exist_ok=True)
    cards, head, buf = [], "intro", []
    for line in pathlib.Path(o.src).read_text(encoding="utf8").splitlines() + ["## "]:
        if line.startswith("## "):
            if "".join(buf).strip():
                cards.append((head, buf))
            head, buf = line[3:].strip(), [line]
        else:
            buf.append(line)
    index = ["# Index", "One card per area. Find the right one with: python ask.py \"<task>\" --map ProjectMap --kw ...", ""]
    for n, (h, body) in enumerate(cards):
        name = slug(h, n)
        (out / name).write_text("\n".join(body).strip() + "\n", encoding="utf8")
        index.append(f"- {name}: {h}")
    (out / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf8")
    print(f"{len(cards)} cards -> {out}")


if __name__ == "__main__":
    main()
