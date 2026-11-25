#!/usr/bin/env python3
"""After `python examples/generate.py`, check the regenerated examples match the committed ones.

Numbers may differ in the last rounding digit between platforms (macOS and Linux math libraries
round a few values differently), so JSON is compared with a small tolerance and text exactly.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def committed(rel):
    return subprocess.check_output(["git", "show", "HEAD:" + rel], cwd=ROOT, text=True)


def load(text, rel):
    if rel.endswith(".js"):
        text = text[text.index("{"):text.rindex("}") + 1]
    return json.loads(text)


def same(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return ["%s: keys differ: %s" % (path, sorted(set(a) ^ set(b)))]
        return [p for k in a for p in same(a[k], b[k], path + "." + str(k))]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return ["%s: length %d vs %d" % (path, len(a), len(b))]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in same(x, y, "%s[%d]" % (path, i))]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if math.isclose(a, b, rel_tol=1e-6, abs_tol=0.051) else ["%s: %r vs %r" % (path, a, b)]
    return [] if a == b else ["%s: %r vs %r" % (path, a, b)]


def main():
    changed = subprocess.check_output(["git", "diff", "--name-only", "--", "examples", "dashboard/data.js"],
                                      cwd=ROOT, text=True).split()
    problems = []
    for rel in changed:
        now = open(os.path.join(ROOT, rel)).read()
        if rel.endswith((".json", ".js")):
            problems += ["%s%s" % (rel, p) for p in same(load(committed(rel), rel), load(now, rel))]
        else:
            problems.append("%s: text differs" % rel)
    for p in problems[:50]:
        print("DIFFERS: " + p)
    print("%d files regenerated with differences, %d real differences" % (len(changed), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
