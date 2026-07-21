from spack_repo.builtin.build_systems.python import PythonPackage
from spack.package import depends_on, license, version


class PyBoutdata(PythonPackage):
    """Python tools for working with BOUT++."""

    homepage = "https://github.com/boutproject/boutdata"
    git = "https://github.com/boutproject/boutdata.git"

    # Set a maintainer if submitting this package to the spack repo
    # maintainers("github_user1", "github_user2")

    license("LGPL-3.0")

    # Release version git tags
    tagged_versions = [
        "0.1.5",
        "0.1.6",
        "0.1.7",
        "0.1.8",
        "0.1.9",
        "0.1.10",
        "0.2.0",
        "0.2.1",
        "0.3.0",
        "0.4.0",
    ]
    for v in tagged_versions:
        version(v, tag=f"v{v}")

    # Treat intermediate versions, mapped to specific Git commits, as release candidates ('rc' suffixes)
    #  - Can be used internally or by consuming packages when inter-release changes break something
    #  - By convention, commit hashes point to master; i.e. the commit where the breaking change was merged in
    #  - If the next release version isn't known - increment the last release version by 0.0.1
    # Format (don't change the line below, as it is used in CI to update package versions!)
    #   version("<next_release_version>rc<date_in_YYYYMMDD>", commit="<git_hash>")
    version("0.4.1rc20260721", commit="a4b429965d15e6e2b09abc8d400ee840d01c1aac")

    # Compatible Python versions
    depends_on("python@3.9:", type=("build", "run"))

    # Build dependencies
    depends_on("py-setuptools@61:", type="build")
    depends_on("py-setuptools-scm@6.2:+toml", type="build")

    # Runtime dependencies
    depends_on("py-boututils", type=("build", "run"))
    depends_on("py-matplotlib@3.2.1:", type=("build", "run"))
    depends_on("py-natsort@8.1.0:", type=("build", "run"))
    depends_on("py-netcdf4", type=("build", "run"))
    depends_on("py-numpy@1.22.0:", type=("build", "run"))
    depends_on("py-scipy@1.4.1:", type=("build", "run"))
    depends_on("py-sympy@1.5.1:", type=("build", "run"))

    def config_settings(self, spec, prefix):
        settings = {}
        return settings
