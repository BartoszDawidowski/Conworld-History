"""worldsim-platec: vendored PyPlatec with extended observational bindings."""

from __future__ import annotations

import sys

from setuptools import Extension, setup

sources = ["platec_src/platecmodule.cpp"]
sources += [
    f"cpp_src/{name}"
    for name in __import__("os").listdir("cpp_src")
    if name.endswith(".cpp")
]

if sys.platform == "win32":
    extra_compile_args = ["/std:c++20"]
else:
    extra_compile_args = ["-std=c++20"]

platec = Extension(
    "platec",
    sources=sources,
    language="c++",
    include_dirs=["cpp_src", "platec_src"],
    extra_compile_args=extra_compile_args,
)

setup(
    name="worldsim-platec",
    version="1.4.3+worldsim.3",
    description="Vendored PyPlatec fork with age/velocity Python bindings for worldsim",
    license="LGPL-3.0-or-later",
    ext_modules=[platec],
    python_requires=">=3.12,<3.13",
)
