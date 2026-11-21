"""Copy the public part of Atlas Chat into a checkout of the public ASM repo.

Run:  python F:\\APP-DEV\\projects\\atlas-chat\\export_public.py F:\\APP-DEV\\projects\\ASM-public

- Copies only files that git tracks AND that public-files.txt allows.
- Never copies a path in core-files.txt or a secret (SECRETS below), and deletes such paths
  from the checkout (old public commits still hold some of them).
- Copies public-overlay/ (LICENSE, NOTICE, README.md) last, to the checkout root.
- Never touches the checkout's .git folder. Never commits or pushes: you check the diff first.
"""
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OVERLAY = "public-overlay/"
# Matched against the file name. Fixed here on purpose: a pattern file is too easy to edit by mistake.
SECRETS = ["settings.json", "settings.local.json", "data.json", "*.log", ".env", ".env.*", "*.env",
           "LICENSE.local", "*.pem", "*.key", "*.pfx", "id_rsa*", "HANDOFF*", "REVIEW-*.md", "*.sqlite*", "*.db"]


def read_patterns(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def matches(rel, patterns):
    return any(fnmatch.fnmatchcase(rel, p) for p in patterns)


def is_private(rel, core):
    return matches(rel, core) or matches(rel.rsplit("/", 1)[-1], SECRETS)


def tracked_files(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def export(dest, root=ROOT, files=None):
    """Copy the public files to dest. Return the list of private paths deleted from dest."""
    dest, root = Path(dest), Path(root)
    core = read_patterns(root / "core-files.txt")
    rules = read_patterns(root / "public-files.txt")
    allow = [p for p in rules if not p.startswith("!")]
    deny = [p[1:] for p in rules if p.startswith("!")]
    files = tracked_files(root) if files is None else files

    removed = []
    for path in sorted(dest.rglob("*")):
        rel = path.relative_to(dest).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not path.is_file():
            continue
        if is_private(rel, core):
            path.unlink()
            removed.append(rel)

    for rel in files:
        if rel.startswith(OVERLAY):
            continue
        if matches(rel, allow) and not matches(rel, deny) and not is_private(rel, core):
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, target)

    for rel in files:
        if rel.startswith(OVERLAY):
            target = dest / rel[len(OVERLAY):]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, target)
    return removed


def main(argv):
    if len(argv) != 2 or not (Path(argv[1]) / ".git").is_dir():
        print("Usage: python export_public.py <path to a git checkout of the ASM repo>")
        return 1
    removed = export(argv[1])
    for rel in removed:
        print("Deleted private file from the checkout:", rel)
    print("Export done. Check it:  git -C", argv[1], "status")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
