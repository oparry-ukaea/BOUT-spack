#!/usr/bin/env python3

import argparse
import json
import pathlib
import re
import subprocess

# Get paths for the hermes directory and the output file from command line args
parser = argparse.ArgumentParser()
parser.add_argument("--hermes-dir", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

# Read dependency version hashes from requirements.txt
requirements_path = pathlib.Path(args.hermes_dir) / "ci" / "requirements.txt"
requirements = requirements_path.read_text()
commits = {}
for python_dependency in ["boutdata", "xbout", "xhermes"]:
    pkg_name = f"py-{python_dependency}"
    m = re.search(
        rf"{python_dependency}\s*@\s*git\+https://github\.com/.+?@([0-9a-f]+)",
        requirements,
    )
    if m:
        commits[pkg_name] = m.group(1)

# Get current Hermes commit and BOUT-dev submodule commit from git directly
commits["hermes-3"] = subprocess.check_output(
    ["git", "-C", args.hermes_dir, "rev-parse", "HEAD"],
    text=True,
).strip()
commits["boutpp"] = subprocess.check_output(
    ["git", "-C", args.hermes_dir, "ls-tree", "HEAD", "external/BOUT-dev"],
    text=True,
).split()[2]

# Write commits dict to the output JSON
with open(args.output, "w") as f:
    json.dump(commits, f, indent=2)
