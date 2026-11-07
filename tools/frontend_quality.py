#!/usr/bin/env python3
"""Format or check the project's Jinja, JavaScript, and CSS frontend sources."""

import argparse
from pathlib import Path
import subprocess
import sys

import cssbeautifier
import jsbeautifier


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"


def formatted_static_files():
    js_options = jsbeautifier.default_options()
    js_options.indent_size = 4
    css_options = cssbeautifier.default_options()
    css_options.indent_size = 4

    for path in sorted(STATIC.glob("*.js")):
        yield path, jsbeautifier.beautify(path.read_text(encoding="utf-8"), js_options).rstrip() + "\n"
    for path in sorted(STATIC.glob("*.css")):
        yield path, cssbeautifier.beautify(path.read_text(encoding="utf-8"), css_options).rstrip() + "\n"


def run_djlint(check):
    failed = False
    for path in sorted(TEMPLATES.glob("*.html")):
        command = [
            sys.executable,
            "-m",
            "djlint",
            str(path),
            "--check" if check else "--reformat",
        ]
        if check:
            command.append("--lint")
        if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
            failed = True
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Report formatting issues without changing files.")
    args = parser.parse_args()

    failed = run_djlint(args.check) != 0
    for path, formatted in formatted_static_files():
        current = path.read_text(encoding="utf-8")
        if current == formatted:
            continue
        if args.check:
            print(f"Would reformat {path.relative_to(ROOT)}")
            failed = True
        else:
            path.write_text(formatted, encoding="utf-8")
            print(f"Reformatted {path.relative_to(ROOT)}")

    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
