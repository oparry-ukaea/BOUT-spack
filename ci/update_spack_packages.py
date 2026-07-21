import argparse
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import spack.paths
from spack.repo import Repo, PATH
from spack.version import Version
from spack.fetch_strategy import GitFetchStrategy
from spack.version import infinity_versions

# script/global scope storage
_git_fetcher_cache = {}
_h3_variant_triggered_dependencies = {"py-xhermes": "xhermes"}
_repo_ref_cache = {}


# ============================== Helper classes ===============================
@dataclass
class GitRefMapper:
    """
    Bi-directional map between git references (branches/tags) and commit hashes.
    """

    ref_to_commit: dict[str, str]
    commit_to_refs: dict[str, list[str]]

    def commit_from_ref(self, ref):
        return self.ref_to_commit.get(ref, None)

    def refs_from_commit(self, commit):
        return self.commit_to_refs.get(commit, [])


# ==============================================================================


# ============================== Helper functions ==============================
def add_hermes_dependency(h3_content, h3_version, dep_name, dep_version):
    """
    Add a new depends_on(...) statement to the hermes-3 package.py file for [dep_name]@[dep_version].
    """

    # Insert the new depends_on(...) line after the last existing one
    dep_pattern = re.compile(
        rf'^\s*depends_on\("{dep_name}".*?\)\s*$',
        re.MULTILINE,
    )
    last_dep_match = None
    for match in dep_pattern.finditer(h3_content):
        last_dep_match = match

    # If no dependency exists (as is the case for py-boutdata), it should be skipped
    if last_dep_match:
        insert_pos = last_dep_match.end()
        print(
            f"Adding new depends_on(...) for [{dep_name}]@[{dep_version}] to hermes-3 package.py"
        )
    else:
        print(
            f"[{dep_name}] isn't a direct dependency of hermes-3; depends_on(...) line won't be added."
        )
        return h3_content

    # Construct the 'depends_on' line
    # Species that hermes versions [h3_version] and onwards require [dep_name]@[dep_version] or higher
    dep_variant = _h3_variant_triggered_dependencies.get(dep_name, "")
    variant_str = f" +{dep_variant}" if dep_variant else ""
    new_dep_line = f'    depends_on("{dep_name}@{dep_version}:", when="@{h3_version}:{variant_str}")\n'
    h3_content = h3_content[:insert_pos] + "\n" + new_dep_line + h3_content[insert_pos:]
    return h3_content


def add_package_version(pkg_class, pkg_content, existing_versions, new_version_commit):
    """
    Add a new version(...) line to [pkg_content] at commit [new_version_commit].
    """
    # Does this commit correspond to a release version?
    # i.e. Does this commit have a git tag, and is that tag 'version-like'?
    is_release = False
    tags = get_git_ref_map(pkg_class).refs_from_commit(new_version_commit)
    if tags:
        if len(tags) > 1:
            print(
                f"WARNING: Multiple git tags found for commit {new_version_commit}: {tags}. Using the first one."
            )
        if is_release_tag(tags[0]):
            release_tag = tags[0]
            is_release = True

    # Add either a new release version or a new rc version
    if is_release:
        pkg_content, new_version = insert_package_release_version(
            pkg_content, release_tag
        )
    else:
        pkg_content, new_version = insert_package_rc_version(
            pkg_content, existing_versions, new_version_commit
        )

    return pkg_content, new_version


# ------------------------------------------------------------------------------
def extract_version_commits(pkg_name, pkg_class):
    """
    Extract a dict of commit_hash-> {"version": version_str, "type": version_type} from the package class.
      version_type is one of "commit", "branch", "tag".
    """
    version_commits = {}
    for version, metadata in pkg_class.versions.items():
        # Skip spack "infinity" versions
        if str(version) in infinity_versions:
            continue

        commit = None
        vtype = "unknown"
        if "commit" in metadata:
            commit = metadata["commit"]
            vtype = "commit"
        else:
            for tag in ["branch", "tag"]:
                if tag in metadata:
                    # Try the reference first, then the version string, then "v" + version string
                    candidate_refs = [
                        metadata[tag],
                        str(version),
                        f"v{str(version)}",
                    ]
                    for ref in candidate_refs:
                        commit = get_git_ref_map(pkg_class).commit_from_ref(ref)
                        if commit is not None:
                            break
                if commit is not None:
                    vtype = tag
                    break

        if commit is None:
            print(
                f"WARNING: Unable to determine commit for {pkg_name}@{version}. Skipping."
            )
        else:
            version_commits[commit] = {"version": version.__str__(), "type": vtype}
    return version_commits


# ------------------------------------------------------------------------------
def get_git_ref_map(pkg_class):
    """
    Generate/retrieve a GitRefMapper for the [pkg_class], preferring a cached version if one exists.
    """

    # Return cached-refs if they already exist
    if pkg_class.git in _repo_ref_cache:
        return _repo_ref_cache[pkg_class.git]

    # Create a spack git-fetcher / retrieve cached version for the relevant repo
    if pkg_class.git not in _git_fetcher_cache:
        _git_fetcher_cache[pkg_class.git] = GitFetchStrategy(git=pkg_class.git)
    fetcher = _git_fetcher_cache[pkg_class.git]

    # Use spack machinery to bare-clone the repo into a cache directory
    cache_dir = (
        Path(spack.paths.user_repos_cache_path)
        / f"ci-version-cache-{abs(hash(pkg_class.git))}"
    )
    if not cache_dir.exists():
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        fetcher.bare_clone(str(cache_dir))

    with working_directory(cache_dir):
        output = fetcher.git(
            "show-ref",
            "--tags",
            "--heads",
            output=str,
        )

    ref_to_commit = {}
    commit_to_refs = defaultdict(list)

    for line in output.splitlines():
        commit, ref = line.split()

        short_ref = ref.removeprefix("refs/tags/")
        short_ref = short_ref.removeprefix("refs/heads/")

        ref_to_commit[short_ref] = commit
        commit_to_refs[commit].append(short_ref)

    # Create the two-way mapper
    result = GitRefMapper(
        ref_to_commit=dict(ref_to_commit),
        commit_to_refs=dict(commit_to_refs),
    )

    # Cache the mapper
    _repo_ref_cache[pkg_class.git] = result

    return result


# ------------------------------------------------------------------------------
def get_pkg_classes(pkg_names, namespace="bout"):
    """
    Read classes from the package repo.
    """
    repo_path = Path(__file__).resolve().parent.parent / "spack_repo" / namespace
    local_repo = Repo(
        str(repo_path),
        cache=PATH.repos[0]._cache,
    )
    return {pkg_name: local_repo.get_pkg_class(pkg_name) for pkg_name in pkg_names}


# ------------------------------------------------------------------------------
def get_rc_version_tag(existing_versions):
    """
    Given a dict of existing versions, return the next rc version tag.
    """
    # Get major, minor, patch for the latest released version
    released_versions = [
        m["version"]
        for m in existing_versions.values()
        if m["type"] in ["sha256", "tag"]
    ]

    latest_released_version = max(released_versions, key=Version)
    major, minor, patch = map(int, latest_released_version.split("."))

    # rc version is current version with patch incremented + "rcYYYYMMDD" suffix
    date_str = datetime.now().strftime("%Y%m%d")

    return f"{major}.{minor}.{patch + 1}rc{date_str}"


# ------------------------------------------------------------------------------
def insert_package_rc_version(pkg_content, existing_versions, new_version_commit):
    """
    Add a new RC version(...) line to package.py.
    """

    new_version = get_rc_version_tag(existing_versions)

    version_line = f'    version("{new_version}", commit="{new_version_commit}")'

    # This should never be true, but just in case...
    if new_version_commit in pkg_content:
        return pkg_content

    # Look for existing RC versions
    rc_pattern = re.compile(
        r'^\s*version\("\d+\.\d+\.\d+rc\d{8}".*?\)\s*$',
        re.MULTILINE,
    )
    matches = list(rc_pattern.finditer(pkg_content))

    if matches:
        # If there are existing RC versions, insert after the last one
        last = matches[-1]
        insert_pos = last.end()
    else:
        # Otherwise, insert on the first new line after the standardised RC version comment
        marker = "next_release_version"
        preamble_end_pos = pkg_content.find(marker)

        if preamble_end_pos < 0:
            raise RuntimeError("Could not find RC version preamble comment")

        insert_pos = pkg_content.find("\n", preamble_end_pos) + 1

    return pkg_content[:insert_pos] + version_line + "\n" + pkg_content[
        insert_pos:
    ], new_version


# ------------------------------------------------------------------------------
def insert_package_release_version(pkg_content, tag):
    """
    Insert a new release version into tagged_versions = [...]
    """

    release_version = tag.removeprefix("v")

    # Locate tagged_versions list
    pattern = re.compile(
        r"(tagged_versions\s*=\s*\[)(.*?)(\])",
        re.DOTALL,
    )
    match = pattern.search(pkg_content)
    if not match:
        raise RuntimeError("Could not find tagged_versions block")
    list_body = match.group(2)

    # Extract existing versions
    versions = re.findall(r'"([^"]+)"', list_body)

    if release_version in versions:
        return pkg_content

    versions.append(release_version)
    versions.sort(key=Version)

    new_body = "".join(f'\n        "{v}",' for v in versions)
    replacement = f"{match.group(1)}{new_body}\n    {match.group(3)}"

    return pkg_content[: match.start()] + replacement + pkg_content[
        match.end() :
    ], release_version


# ------------------------------------------------------------------------------
def is_release_tag(tag):
    """
    Check if a git tag has the form of a release version (vX.Y.Z or X.Y.Z, where X, Y, and Z are integers).
    """
    pattern = r"^v?\d+\.\d+\.\d+$"
    return re.match(pattern, tag) is not None


# ------------------------------------------------------------------------------
def read_pkg_files(pkg_classes):
    """
    Read package.py for each package in the <pkg_classes> dict and return the contents in another dict.
    """
    pkgs_content = {}
    for pkg_name, pkg_class in pkg_classes.items():
        pkgfile = Path(pkg_class.package_dir) / "package.py"
        if not pkgfile.exists():
            print(
                f"WARNING: Package file for {pkg_name} not found at [{pkgfile}]!? Skipping."
            )
            continue
        pkgs_content[pkg_name] = pkgfile.read_text()
    return pkgs_content


# ------------------------------------------------------------------------------
@contextmanager
def working_directory(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


# =============================================================================
def main():

    # Read commits json
    parser = argparse.ArgumentParser()
    parser.add_argument("--commits_file", required=True)
    args = parser.parse_args()

    with open(args.commits_file) as f:
        commits = json.load(f)

    # Get all the package classes
    pkg_classes = get_pkg_classes(commits.keys())

    # Read all the package files
    all_content = read_pkg_files(pkg_classes)

    # Extract versions
    all_version_commits = {
        pkg_name: extract_version_commits(pkg_name, pkg_class)
        for pkg_name, pkg_class in pkg_classes.items()
    }

    # Separate the hermes commit; everything else is a dependency
    hermes_commit = commits.pop("hermes-3")

    # Add any new versions of dependencies to their respective package.py files
    new_dependency_versions = {}
    for dep_name, commit in commits.items():
        pkg_version_commits = all_version_commits.get(dep_name, {})
        if commit in pkg_version_commits:
            print(
                f"Commit [{commit}] of [{dep_name}] already registered as version [{pkg_version_commits[commit]['version']}]."
            )
        else:
            all_content[dep_name], dep_version = add_package_version(
                pkg_classes[dep_name],
                all_content[dep_name],
                pkg_version_commits,
                commit,
            )
            print(
                f"ADDED commit [{commit}] as version [{dep_version}] of [{dep_name}]."
            )
            new_dependency_versions[dep_name] = dep_version

    # Add depends_on(...) statements to the hermes package file if necessary
    if new_dependency_versions:
        existing_hermes_versions = extract_version_commits(
            "hermes-3", pkg_classes["hermes-3"]
        )
        # If there are new dependencies, we need a new hermes version at the current commit
        print(f"Adding new hermes-3 version at commit [{hermes_commit}]")
        all_content["hermes-3"], new_hermes_version = add_package_version(
            pkg_classes["hermes-3"],
            all_content["hermes-3"],
            existing_hermes_versions,
            hermes_commit,
        )

        for dep_name, dep_version in new_dependency_versions.items():
            all_content["hermes-3"] = add_hermes_dependency(
                all_content["hermes-3"], new_hermes_version, dep_name, dep_version
            )

    # Write out all the modified package.py files
    for dep_name, content in all_content.items():
        pkgfile = Path(pkg_classes[dep_name].package_dir) / "package.py"
        pkgfile.write_text(content)


# =============================================================================

if __name__ == "__main__":
    main()
