# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.cmake import CMakePackage
from spack.error import InstallError
from spack.package import depends_on, license, maintainers, variant, version
import spack.repo


def check_pkg_available(_unused1, variant_name, _unused2, raise_on_notfound=True):
    """Validator function to check that packages (particularly 'Reactions') are known to spack."""
    if not spack.repo.PATH.exists(variant_name):
        if raise_on_notfound:
            err_msg = f"Package '{variant_name}' does not exist in any known package repository."
            if variant_name == "vantagereactions":
                err_msg += "\nNote that building hermes-3 with +vantagereactions currently requires spack to be pointed to the packages inside a local copy of the https://github.com/UKAEA-Edge-Code/VANTAGE-Reactions git repo."
            raise InstallError(err_msg)
        else:
            return False
    else:
        return True


def vantagereactions_pkg_available():
    return check_pkg_available("", "vantagereactions", "", raise_on_notfound=False)


class Hermes3(CMakePackage):
    """A multifluid magnetized plasma simulation model.

    Hermes-3 is built on the BOUT++ framework, and uses a system of reusable components
    to build models at runtime based on input configuration, in 1D, 2D or 3D curvlinear
    coordinates."""

    homepage = "https://hermes3.readthedocs.io/"
    git = "https://github.com/boutproject/hermes-3.git"

    maintainers("bendudson")

    license("GPL-3.0-or-later")

    version("develop", branch="develop")
    version("master", branch="master", submodules=True, preferred=True)

    # Release versions
    tagged_versions = ["1.2.0", "1.2.1", "1.3.0", "1.3.1", "1.4.0", "1.4.1"]
    for v in tagged_versions:
        version(v, tag=f"v{v}", submodules=True)

    # Treat intermediate versions, mapped to specific Git commits, as release candidates ('rc' suffixes)
    #  - Can be used internally or by consuming packages when inter-release changes break something
    #  - By convention, commit hashes point to master; i.e. the commit where the breaking change was merged in
    #  - If the next release version isn't known - increment the last release version by 0.0.1
    # Format (don't change the line below, as it is used in CI to update package versions!)
    #   version("<next_release_version>rc<date_in_YYYYMMDD>", commit="<git_hash>")
    version("1.4.2rc20260212", commit="1ee1c190742ed36470776d0bcf188aad33754bd0")
    version("1.4.2rc20260615", commit="c8aa7969ee288862a5af3201db61d932ff64b377")

    version("1.4.2rc20260721", commit="731e64498026a1b9ca3152da73c14b8c0e78950e")
    variant(
        "limiter",
        default="MC",
        description="Slope limiter",
        values=("MC", "MinMod"),
        multi=False,
    )
    variant(
        "xhermes", default=True, description="Builds xhermes (required for some tests)."
    )
    variant(
        "vantagereactions",
        default=False,
        description="Build Hermes-3 with VANTAGE-Reactions suppport.",
        validator=check_pkg_available,
    )
    variant(
        "updatesubmodules",
        default=False,
        description="Update submodules during build",
    )

    depends_on("c", type="build")
    depends_on("cxx", type="build")
    depends_on("cmake@3.24:", type="build")
    depends_on("fftw", type=("build", "link"))
    depends_on("mpi", type=("build", "link", "run"))
    depends_on("boutpp", type=("build", "link"))
    depends_on("boutpp@5.2.1rc20260721:", when="@1.4.2rc20260721:")

    depends_on("netcdf-cxx4", type=("build", "link"))
    # Need boutdata for boutupgrader script, even when not installing xhermes
    depends_on("py-boutdata@0.3.0:", type=("run"))

    # Variant-controlled dependencies
    depends_on("py-xhermes", when="+xhermes", type=("run"))
    depends_on("py-xhermes@0.1.1:", when="@1.4.2rc20260212: +xhermes")
    depends_on("py-xhermes@0.1.2rc20260611:", when="@1.4.2rc20260615: +xhermes")

    if vantagereactions_pkg_available():
        depends_on("vantagereactions", when="+vantagereactions", type=("build", "link"))
        depends_on("petsc+hdf5+mpi", when="+vantagereactions", type=("build", "link"))
        depends_on("py-h5py", when="+vantagereactions", type=("run"))
        depends_on("py-petsc4py", when="+vantagereactions", type=("run"))
        depends_on("neso-rng-toolkit", when="+vantagereactions", type=("build", "link"))
        

    def cmake_args(self):
        # Definitions controlled by variants
        variant_defs = {
            "HERMES_SLOPE_LIMITER": "limiter",
            "HERMES_USE_VANTAGE": "vantagereactions",
            "HERMES_UPDATE_GIT_SUBMODULE": "updatesubmodules",
        }
        variant_args = [
            self.define_from_variant(def_str, var_str)
            for def_str, var_str in variant_defs.items()
        ]

        fixed_args = [self.define("HERMES_BUILD_BOUT", False)]

        # Concatenate different arg types and return
        args = []
        args.extend(fixed_args)
        args.extend(variant_args)

        return args
