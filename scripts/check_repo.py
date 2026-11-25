#!/usr/bin/env python3
"""Repository checks CI runs on every push. Standard library only.

1. Every SKILL.md has YAML front matter with a quoted name and description (a bare ": " in an
   unquoted description breaks GitHub's renderer and the plugin loader).
2. Every relative path a skill or reference mentions (`../../reference/x.md` and the like) exists.
3. Both example plans validate with no errors.
4. No personal data: the files that must stay out of the repository are absent, and no tracked file
   contains a pattern from the private-patterns list (an email address, or the extra patterns in
   STRIDER_PII_PATTERNS, newline separated, which a maintainer can set as a CI secret).
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from strider import plan as P  # noqa: E402

problems = []


def front_matter():
    for path in sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))):
        text = open(path).read()
        rel = os.path.relpath(path, ROOT)
        if not text.startswith("---\n"):
            problems.append("%s: no front matter" % rel)
            continue
        head = text[4:text.index("\n---", 4)]
        fields = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
        for key in ("name", "description"):
            if key not in fields:
                problems.append("%s: front matter has no %s" % (rel, key))
        desc = fields.get("description", "").strip()
        if desc and not (desc.startswith('"') and desc.endswith('"')):
            problems.append("%s: description must be double-quoted" % rel)
        if fields.get("name", "").strip() != os.path.basename(os.path.dirname(path)):
            problems.append("%s: name does not match its folder" % rel)


def links():
    pat = re.compile(r"`((?:\.\./)+[\w./-]+\.(?:md|json|py|html))`")
    for path in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")) + glob.glob(os.path.join(ROOT, "reference", "*.md")):
        for m in pat.finditer(open(path).read()):
            target = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
            if not os.path.exists(target):
                problems.append("%s: %s does not exist" % (os.path.relpath(path, ROOT), m.group(1)))


def examples():
    for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*", "plan.json"))):
        plan = P.load(path)
        errors, _ = P.validate(plan)
        if errors:
            problems.append("%s: %d validation errors, first: %s" % (os.path.relpath(path, ROOT), len(errors), errors[0]))
        if plan.get("synthetic") is not True:
            problems.append("%s: example plan is not marked synthetic" % os.path.relpath(path, ROOT))


ALLOWED_EMAILS = ("noreply@anthropic.com",)


def personal_data():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).split()
    for banned in ("athlete.md", "plan.json", "plan.ics", "decisions.md"):
        if banned in tracked:
            problems.append("%s is tracked at the repository root; it holds a runner's own data" % banned)
    if any(t.startswith("data/") for t in tracked):
        problems.append("data/ is tracked; raw Garmin data never belongs in the repository")
    extra = [p for p in os.environ.get("STRIDER_PII_PATTERNS", "").splitlines() if p.strip()]
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    for rel in tracked:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path) or rel.endswith((".png", ".jpg", ".fit")):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for m in email.finditer(text):
            if m.group(0) not in ALLOWED_EMAILS and not m.group(0).endswith("users.noreply.github.com"):
                problems.append("%s: email address %s" % (rel, m.group(0)))
        for p in extra:
            if re.search(p, text, re.I):
                problems.append("%s: matches a private pattern" % rel)


if __name__ == "__main__":
    front_matter()
    links()
    examples()
    personal_data()
    for p in problems:
        print("FAIL: " + p)
    print("%d problems" % len(problems))
    sys.exit(1 if problems else 0)
