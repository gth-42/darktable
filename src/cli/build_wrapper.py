#!/usr/bin/env python3
"""
Phase 1 cffi wrapper for darktable-cli.
Wraps dt_cli_process_simple() for Python access.
"""

from cffi import FFI

ffibuilder = FFI()

# Define the C function signature
ffibuilder.cdef("""
    int dt_cli_process_simple(const char *input_path,
                              const char *output_path,
                              int width,
                              int height);
""")

# Set up the source - link against our wrapper library
ffibuilder.set_source(
    "_dt_cli_wrapper",
    """
    // External declaration from libdt_cli_wrapper.so
    extern int dt_cli_process_simple(const char *input_path,
                                     const char *output_path,
                                     int width,
                                     int height);
    """,
    libraries=['dt_cli_wrapper', 'darktable'],
    library_dirs=[
        '/mnt/2t4/development/darktable/darktable/src/cli',
        '/home/glen/Applications/Darktable/lib/darktable'
    ],
    runtime_library_dirs=[
        '/mnt/2t4/development/darktable/darktable/src/cli',
        '/home/glen/Applications/Darktable/lib/darktable'
    ]
)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
