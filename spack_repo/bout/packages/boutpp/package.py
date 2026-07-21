# Copyright 2013-2024 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (LGPL-3.0-only)

# ----------------------------------------------------------------------------

from spack_repo.builtin.build_systems.cmake import CMakePackage
from spack.package import conflicts, depends_on, license, maintainers, patch, variant, version


class Boutpp(CMakePackage):
    """BOUT++ is a framework for writing fluid and plasma simulations in curvilinear geometry. It is intended to be quite modular, with a variety of numerical methods and time-integration solvers available. BOUT++ is primarily designed and tested with reduced plasma fluid models in mind, but it can evolve any number of equations, with equations appearing in a readable form."""

    homepage = "https://bout-dev.readthedocs.io"
    git = "https://github.com/boutproject/BOUT-dev"
    url = "https://github.com/boutproject/BOUT-dev/releases/download/v5.1.0/BOUT++-v5.1.0.tar.gz"

    maintainers("oparry-ukaea")

    license("LGPL-3.0-only")

    version("develop", branch="next", submodules=True)
    version("master", branch="master", submodules=True, preferred=True)

    # Include tagged versions that use CMake (5.0.0 onwards)
    tagged_versions = ["5.0.0", "5.1.0", "5.1.1", "5.2.0"]
    for v in tagged_versions:
        version(v, tag=f"v{v}", submodules=True)

    # Treat intermediate versions, mapped to specific Git commits, as release candidates ('rc' suffixes)
    #  - Can be used internally or by consuming packages when inter-release changes break something
    #  - By convention, commit hashes point to master; i.e. the commit where the breaking change was merged in
    #  - If the next release version isn't known - increment the last release version by 0.0.1
    # Format (don't change the line below, as it is used in CI to update package versions!)
    #   version("<next_release_version>rc<date_in_YYYYMMDD>", commit="<git_hash>")
    version("5.2.1rc20260721", commit="2384555b6ad9763cddc3e99a99ed4c4c1037faa2")

    # Patches
    patch("fix_thirdparty_cmake_v5.0.0.patch", when="@5.0.0")
    patch("fix_thirdparty_cmake_v5.1.x.patch", when="@5.1")

    # Variants
    variant("adios2", default=False, description="Builds with ADIOS2 support.")
    variant("backtrace", default=True, description="Enable backtrace.")
    variant("builddocs", default=False, description="Builds the documentation.")
    variant("buildexamples", default=False, description="Builds the examples.")
    variant(
        "buildtests",
        description="Choose whether to build the standard set of tests ('default'), the complete set ('all'), or none at all ('none').",
        values=("all", "default", "none"),
        default="none",
        multi=True,
    )
    variant("caliper", default=False, description="Builds with Caliper support.")
    variant(
        "check",
        description="Sets the CHECK variable which controls the level of internal runtime checking.",
        values=("0", "1", "2", "3", "4"),
        default="2",
        multi=True,
    )
    variant("cuda", default=False, description="Builds with CUDA support.")
    variant("fftw", default=True, description="Builds with FFTW support.")
    variant("hypre", default=False, description="Builds with Hypre support.")
    variant("lapack", default=False, description="Builds with LAPACK support.")
    variant("metric3d", default=False, description="Enable 3D metric support.")
    variant("netcdf", default=True, description="Enable support for NetCDF output.")
    variant("openmp", default=False, description="Enable OpenMP support.")
    variant("petsc", default=False, description="Builds with PETSc support.")
    variant("python", default=False, description="Builds with Python support.")
    variant("raja", default=False, description="Builds with RAJA support.")
    variant("sanitize_address", default=False, description="Enable address sanitizer.")
    variant("sanitize_leak", default=False, description="Enable leak sanitizer.")
    variant("sanitize_memory", default=False, description="Enable memory sanitizer.")
    variant("sanitize_thread", default=False, description="Enable thread sanitizer.")
    variant(
        "sanitize_undefined",
        default=False,
        description="Enable undefined behavior sanitizer.",
    )
    variant("scorep", default=False, description="Builds with Score-P support.")
    variant("slepc", default=False, description="Builds with SLEPC support.")
    variant("shared", default=True, description="Build shared libraries.")
    variant("sigfpe", default=False, description="Signal floating point exceptions.")
    variant("signal", default=True, description="Signal handling.")
    variant("sundials", default=False, description="Builds with SUNDIALS support.")
    variant("track", default=True, description="Enable field name tracking.")
    variant("umpire", default=False, description="Builds with Umpire support.")
    variant("uuid", default=True, description="Use system UUID generator")
    variant("updatesubmodules", default=False, description="Update submodules during build")
    # Fixed dependencies
    depends_on("c", type="build")
    depends_on("cxx", type="build")
    depends_on("cmake@3.17:", type="build")
    depends_on("mpi", type=("build", "link", "run"))

    # Simple build dependencies
    # Derived from variants with the same name, an optional version specifier, but no special variant options of their own
    simple_deps = [
        "adios2",
        "caliper",
        "cuda",
        "fftw",
        "hypre",
        "lapack",
        "python",
        "raja",
        "scorep",
        "slepc",
        "sundials",
        "umpire",
    ]
    simple_dep_versions = {"sundials": "2.6:6.7.0"}
    for dep in simple_deps:
        dep_spec = (
            dep
            if not dep in simple_dep_versions
            else f"{dep}@{simple_dep_versions[dep]}"
        )
        depends_on(dep_spec, type=("build", "link"), when=f"+{dep}")

    # Other dependencies affected by variants
    depends_on("netcdf-cxx4", type=("build", "link"), when="+netcdf")
    depends_on("py-cython", type=("build", "link"), when="+python")
    depends_on("py-jinja2", type=("build", "link"), when="+python")
    depends_on("py-numpy", type=("build", "link"), when="+python")

    # PETSc dependency
    #   Always use MPI and specify supported version range (across all BOUT versions)
    depends_on("petsc@3.7:3.23+mpi", type=("build", "link"), when="+petsc")
    # BOUT v5.0.0 won't build with PETSc v3.18 onwards
    conflicts("petsc@3.18:", when="+petsc@:5.0.0")

    def cmake_args(self):
        # Definitions controlled by variants
        variant_defs = {
            "BOUT_USE_ADIOS2": "adios2",
            "BOUT_ENABLE_BACKTRACE": "backtrace",
            "BOUT_BUILD_DOCS": "builddocs",
            "BOUT_BUILD_EXAMPLES": "buildexamples",
            "BOUT_ENABLE_CALIPER": "caliper",
            "CHECK": "check",
            "BOUT_ENABLE_CUDA": "cuda",
            "BOUT_USE_HYPRE": "hypre",
            "BOUT_USE_LAPACK": "lapack",
            "BOUT_ENABLE_METRIC_3D": "metric3d",
            "BOUT_USE_NETCDF": "netcdf",
            "BOUT_ENABLE_OPENMP": "openmp",
            "BOUT_USE_PETSC": "petsc",
            "BOUT_ENABLE_PYTHON": "python",
            "BOUT_ENABLE_RAJA": "raja",
            "ENABLE_SANITIZER_ADDRESS": "sanitize_address",
            "ENABLE_SANITIZER_LEAK": "sanitize_leak",
            "ENABLE_SANITIZER_MEMORY": "sanitize_memory",
            "ENABLE_SANITIZER_THREAD": "sanitize_thread",
            "ENABLE_SANITIZER_UNDEFINED_BEH": "sanitize_undefined",
            "BOUT_USE_SCOREP": "scorep",
            "BOUT_USE_SLEPC": "slepc",
            "BUILD_SHARED_LIBS": "shared",
            "BOUT_ENABLE_SIGFPE": "sigfpe",
            "BOUT_ENABLE_SIGNAL": "signal",
            "BOUT_USE_SUNDIALS": "sundials",
            "BOUT_ENABLE_TRACK": "track",
            "BOUT_ENABLE_UMPIRE": "umpire",
            "BOUT_USE_UUID_SYSTEM_GENERATOR": "uuid",
            "BOUT_UPDATE_GIT_SUBMODULE": "updatesubmodules",
        }
        variant_args = [
            self.define_from_variant(def_str, var_str)
            for def_str, var_str in variant_defs.items()
        ]

        # Build tests unless variant buildtests=none
        variant_args.append(
            self.define(
                "BOUT_TESTS", self.spec.variants["buildtests"].value[0] != "none"
            )
        )
        # Build ALL tests if variant buildtests=all
        variant_args.append(
            self.define(
                "BOUT_ENABLE_ALL_TESTS",
                self.spec.variants["buildtests"].value[0] == "all",
            )
        )

        # Always use these definitions
        fixed_args = [
            # Don't download any dependencies (use spack to resolve them instead)
            self.define("BOUT_DOWNLOAD_ADIOS2", False),
            self.define("BOUT_DOWNLOAD_NETCDF_CXX4", False),
            self.define("BOUT_DOWNLOAD_SUNDIALS", False),
            # Always build with MPI
            self.define("BOUT_ENABLE_MPI", True),
            # Avoid any confusion between conda and spack
            self.define("BOUT_IGNORE_CONDA_ENV",True),
            # Ensure bout submodules are up to date before building
            self.define("BOUT_UPDATE_GIT_SUBMODULE", True),
            # Always build with PVODE
            self.define("BOUT_USE_PVODE", True),
            # Don't install gtest (resolve dependency with spack instead)
            self.define("INSTALL_GTEST", False),
        ]
        # There are problems with how CMake finds the glibc/standalone versions
        # of gettext (see
        # https://github.com/boutproject/hermes-3/issues/356#issuecomment-2999715879).
        # Workaround is to turn off natural language support for now.
        fixed_args.append(self.define("BOUT_USE_NLS", False))

        # Concatenate different arg types and return
        args = []
        args.extend(fixed_args)
        args.extend(variant_args)

        return args
