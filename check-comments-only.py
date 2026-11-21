"""Check that a branch only adds or changes comments, never code.

Use: python check-comments-only.py <base-ref>
Example: python check-comments-only.py origin/claude/funny-fermi-qpy08t

Python files: the code with docstrings removed must be the same before and after (compared with ast).
Other text files (.js .ts .tsx .rs .html .css .ps1): every added or removed line must be blank or a comment.
Exit code 0 = only comments changed. Exit code 1 = a code change was found, and the file is named.
"""
import ast
import re
import subprocess
import sys

COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|\*/|#|<!--|-->|$)")
TEXT_EXT = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rs", ".html", ".css", ".ps1")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def show(ref, path):
    try:
        return git("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None  # the file does not exist on that side


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def python_same(old, new):
    try:
        return strip_docstrings(ast.parse(old)) == strip_docstrings(ast.parse(new))
    except SyntaxError:
        return False


def text_only_comments(base, path):
    diff = git("diff", "-U0", base, "HEAD", "--", path)
    for line in diff.splitlines():
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        if not COMMENT_LINE.match(line[1:]):
            return line
    return None


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    bad = []
    for path in git("diff", "--name-only", base, "HEAD").splitlines():
        old, new = show(base, path), show("HEAD", path)
        if old is None or new is None:
            bad.append(f"{path}: file was added or deleted")
        elif path.endswith(".py"):
            if not python_same(old, new):
                bad.append(f"{path}: Python code changed (not only comments or docstrings)")
        elif path.endswith(TEXT_EXT):
            line = text_only_comments(base, path)
            if line:
                bad.append(f"{path}: code line changed: {line[:120]}")
        elif not path.endswith(".md"):
            bad.append(f"{path}: file type not checked, look at it by hand")
    for b in bad:
        print("NOT ONLY COMMENTS:", b)
    if not bad:
        print("OK: only comments and docstrings changed.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
