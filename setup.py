#!/usr/bin/env python3

import sys

import setuptools


ext_modules = []

if sys.platform == "darwin":
    ext_modules.append(
        setuptools.Extension(
            "hgext3rd.credentials.keychain",
            sources=["hgext3rd/credentials/keychain.m"],
            py_limited_api=True,
            define_macros=[
                ("PY_SSIZE_T_CLEAN", 1),
            ],
            extra_compile_args=[
                "-Wall",
                "-Wextra",
                "-gfull",
                "-fobjc-arc",
                "-Wno-unused-parameter",
                "-Wno-missing-field-initializers",
            ],
            extra_link_args=[
                "-framework",
                "Foundation",
                "-framework",
                "Security",
            ],
        ),
    )


if __name__ == "__main__":
    setuptools.setup(
        ext_modules=ext_modules,
    )
