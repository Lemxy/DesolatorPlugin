"""Prepare bench/work: shallow clones of the public repos, one copy per arm.
work/base/<repo>: plain checkout. work/full/<repo>: same plus `slim.py code` deny rules.
Usage: python bench/setup_e2e.py [--repos requests,flask,django]"""
import argparse, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = HERE / "work"
REPOS = {"requests": "psf/requests", "flask": "pallets/flask", "django": "django/django"}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--repos", default=",".join(REPOS))
    o = a.parse_args()
    for name in o.repos.split(","):
        src = WORK / "src" / name
        if not src.exists():
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{REPOS[name]}.git", str(src)], check=True)
        for arm in ("base", "full"):
            dst = WORK / arm / name
            shutil.rmtree(dst, ignore_errors=True)
            # no .git: the agent must not browse history
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"))
        subprocess.run([sys.executable, str(ROOT / "slim.py"), "code"], cwd=WORK / "full" / name, check=True)
        print("ready:", name)


if __name__ == "__main__":
    main()
