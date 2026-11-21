"""Safe update for Atlas Chat on the PC. It checks first and changes last.

    python get_update.py                 show the state and what can be merged. Changes nothing.
    python get_update.py <branch>        bring that branch from GitHub into the branch you are on.
    python get_update.py <branch> --yes  the same, without the question.

Why this exists: on 2026-11-10 a cloud session built a feature on an old copy of the app and
told Jason to "git checkout" that branch. His project folder switched to the old app.
This script makes that mistake impossible:
  - it never switches branch;
  - it refuses a branch that does not hold the desktop app;
  - it refuses when files have unsaved changes;
  - it only moves forward (fast-forward). It never rewrites or mixes history.
Standard library only.
"""
import subprocess
import sys

APP_MARK = "atlas-rust-desktop/src-tauri/tauri.conf.json"  # only the real desktop app has this file


class Stop(Exception):
    """A check failed. The message says what to do."""


def git(*args, cwd=None, check=True):
    run = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and run.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed:\n{run.stderr.strip() or run.stdout.strip()}")
    return run.stdout.strip() if check else run


def has_app(ref, cwd=None):
    return git("cat-file", "-e", f"{ref}:{APP_MARK}", cwd=cwd, check=False).returncode == 0


def is_ancestor(old, new, cwd=None):
    return git("merge-base", "--is-ancestor", old, new, cwd=cwd, check=False).returncode == 0


def checks(cwd=None, fetch=True):
    """The checks that run before anything else. Returns the current branch name."""
    if git("rev-parse", "--is-inside-work-tree", cwd=cwd, check=False).returncode != 0:
        raise Stop("This folder is not a git project. Go to the Atlas project folder first (the one that holds get_update.py).")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch == "HEAD":
        raise Stop("No branch is checked out (detached HEAD). Run:  git checkout <your app branch>")
    if not has_app("HEAD", cwd):
        raise Stop(f"You are on \"{branch}\", which does NOT hold the desktop app (old version of Atlas).\n"
                   "Go back to the branch you were on:  git checkout -\n"
                   "Then run this script again.")
    changed = git("status", "--porcelain", "--untracked-files=no", cwd=cwd)
    if changed:
        raise Stop("These files have changes that are not committed:\n" + "\n".join("  " + l.strip() for l in changed.splitlines()) +
                   "\nDo NOT commit them: a commit of your own stops this script, because it only moves forward.\n"
                   "  - You changed them on purpose: tell Claude which files, so the change is put in the update.\n"
                   "  - You did not: undo it with  git restore -- <the files above>\n"
                   "Then run this script again.")
    if fetch:
        if not git("remote", cwd=cwd):
            raise Stop("This project has no link to GitHub. Run:\n  git remote add origin https://github.com/noprivacynofreedom/atlas-chat")
        git("fetch", "--prune", "origin", cwd=cwd)
    return branch


def survey(branch, cwd=None):
    """Remote branches that hold work you do not have: (name, commits ahead, date, verdict)."""
    rows = []
    for ref in git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", cwd=cwd).splitlines():
        name = ref.split("/", 1)[1] if "/" in ref else ref
        if name in ("HEAD", "") or ref == "origin":
            continue
        ahead = int(git("rev-list", "--count", f"HEAD..{ref}", cwd=cwd))
        if not ahead:
            continue
        date = git("log", "-1", "--format=%cs", ref, cwd=cwd)
        if not has_app(ref, cwd):
            verdict = "DO NOT USE: old version of Atlas, no desktop app in it"
        elif not is_ancestor("HEAD", ref, cwd):
            verdict = "cannot merge by itself: it does not contain your newest work. Ask Claude to rebuild it on your branch"
        else:
            verdict = f"OK. To get it:  python get_update.py {name}"
        rows.append((name, ahead, date, verdict))
    return sorted(rows, key=lambda r: r[2], reverse=True)


def classify_changes(before, after, cwd=None):
    """Return 'resources' if only backend/UI resources (or docs/tests) changed, else 'native'."""
    changed = [p for p in git("diff", "--name-only", f"{before}..{after}", cwd=cwd).splitlines() if p]
    native_prefixes = ("atlas-rust-desktop/src/", "atlas-rust-desktop/src-tauri/src/",
                       "atlas-rust-desktop/src-tauri/nsis/", "atlas-rust-desktop/package")
    native_files = ("atlas-rust-desktop/src-tauri/Cargo.toml", "atlas-rust-desktop/src-tauri/Cargo.lock",
                    "atlas-rust-desktop/src-tauri/tauri.conf.json", "atlas-rust-desktop/index.html")
    for path in changed:
        if path.startswith(native_prefixes) or path in native_files:
            return "native"
    return "resources"


def update(name, cwd=None, yes=False, ask=input, out=print):
    branch = checks(cwd)
    name = name[len("origin/"):] if name.startswith("origin/") else name
    ref = f"origin/{name}"
    if git("rev-parse", "--verify", "--quiet", ref, cwd=cwd, check=False).returncode != 0:
        raise Stop(f"GitHub has no branch named \"{name}\". Run  python get_update.py  to see the names.")
    if not has_app(ref, cwd):
        raise Stop(f"\"{name}\" does NOT hold the desktop app. It is an old version of Atlas.\n"
                   "Nothing was changed. Tell Claude: \"rebuild this on my app branch " + branch + "\".")
    ahead = int(git("rev-list", "--count", f"HEAD..{ref}", cwd=cwd))
    if not ahead:
        out(f"Nothing to do: \"{branch}\" already has everything from \"{name}\".")
        return False
    if not is_ancestor("HEAD", ref, cwd):
        raise Stop(f"\"{name}\" does not contain your newest work on \"{branch}\", so it cannot be added safely.\n"
                   "Nothing was changed. Tell Claude: \"rebuild this on top of " + branch + "\".")
    out(f"You are on: {branch}\nIncoming:   {name} ({ahead} new commits)\n")
    out(git("log", "--format=  %cs  %s", f"HEAD..{ref}", cwd=cwd))
    out("\nFiles that change:\n" + git("diff", "--stat", f"HEAD..{ref}", cwd=cwd))
    if not yes and ask(f"\nAdd these to \"{branch}\"? [y/N] ").strip().lower() not in ("y", "yes"):
        out("Cancelled. Nothing was changed.")
        return False
    before = git("rev-parse", "--short", "HEAD", cwd=cwd)
    git("merge", "--ff-only", ref, cwd=cwd)
    kind = classify_changes(before, "HEAD", cwd=cwd)
    if kind == "resources":
        next_steps = (
            "Next steps (Python/UI only changed — no Rust rebuild needed):\n"
            "  1. Fast rollout (seconds): .\\sync-live.ps1 -CloseApp -Launch\n"
            "  2. Or full installer:      .\\build-release.ps1"
        )
    else:
        next_steps = (
            "Next steps (Rust or desktop frame changed):\n"
            "  1. Fast local rollout:     .\\sync-live.ps1 -BuildExe -CloseApp -Launch\n"
            "  2. Or full installer:      .\\build-release.ps1\n"
            "  3. Start Atlas Chat from the Start menu."
        )
    out(f"\nDone. \"{branch}\" now has the new work. You did not switch branch.\n"
        f"To undo:  git reset --hard {before}\n\n" + next_steps)
    return True


def main(argv):
    args = [a for a in argv if not a.startswith("-")]
    try:
        if args:
            update(args[0], yes="--yes" in argv or "-y" in argv)
            return 0
        branch = checks()
        print(f"You are on: {branch}  (holds the desktop app: yes, no uncommitted changes)\n")
        rows = survey(branch)
        if not rows:
            print("You are up to date. No branch on GitHub has work that you do not have.")
        for name, ahead, date, verdict in rows:
            print(f"{name}\n    {ahead} new commits, newest {date}\n    {verdict}\n")
        return 0
    except Stop as e:
        print("STOPPED. Nothing was changed.\n" + str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
